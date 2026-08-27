import asyncio
import contextlib
import json
import logging
import os
import secrets

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.websocket import WS_CLOSE_IDLE, receive_or_idle
from app.container import build_application
from app.config import config
from app.database import init_db
from app.utils.paths import resolve_within

# Logging is configured in app/__init__.py, before these imports execute.
logger = logging.getLogger(__name__)

init_db()

# The composition root builds the service graph; this module only routes.
_application = build_application()
manager = _application.manager


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    """Warm the emotion model without holding up the port bind.

    Warm-up used to run during import, so uvicorn could not bind its socket
    until TensorFlow had finished loading and building the model. On a small
    shared CPU that is tens of seconds during which the host sees a container
    that is not listening -- and hosts bound that: Cloud Run allows at most 4
    minutes for container startup before it calls the revision failed.

    It cannot go directly in this lifespan handler either: uvicorn runs lifespan
    startup to completion *before* it binds. So it is dispatched to a worker
    thread (it is synchronous, CPU-bound TensorFlow work) and simply left to
    finish on its own. `/api/health` answers immediately; a frame that arrives
    first waits for the same build via EmotionService.warm_up.
    """
    task = asyncio.create_task(asyncio.to_thread(_application.warm_up))
    try:
        yield
    finally:
        # On shutdown, stop waiting on a warm-up that may still be running --
        # but surface anything it raised rather than dropping it silently.
        if not task.done():
            task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Polly AI Debate Coach", lifespan=lifespan)

# CORS middleware — explicit origins only; "*" with allow_credentials=True is
# invalid per the CORS spec and over-permissive (issue #22).
# The module-level TopicService instance that used to live here is gone: topic
# assignment moved into ConnectionManager.assign_new_topic, which guards against
# the session having disappeared.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


async def _handle_message(session_id: str, message: dict) -> None:
    """Route one decoded client message to its handler."""
    message_type = message.get("type")

    if message_type == "frame":
        await manager.process_frame(session_id, message.get("data"), message.get("timestamp"))
    elif message_type == "start_recording":
        await manager.start_recording(session_id)
    elif message_type == "stop_recording":
        await manager.stop_recording(session_id)
    elif message_type == "audio_complete":
        await manager.process_audio_chunk(session_id, message.get("data"))
    elif message_type == "chat":
        await manager.process_chat_message(session_id, message.get("message"))
    elif message_type == "request_new_topic":
        await manager.assign_new_topic(session_id)
    elif message_type == "ping":
        # Deliberately does nothing. Its only job is to have arrived: receiving
        # it resets the idle timer, which is how a user sitting on the page with
        # the camera off avoids having their session reaped mid-read.
        pass
    else:
        logger.warning("Unknown message type %r from session %s", message_type, session_id)
        await manager.send_message(session_id, {
            "type": "error",
            "message": f"Unknown message type: {message_type}",
        })


# Length of a server-minted session id, in bytes of entropy before encoding.
SESSION_ID_BYTES = 24


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Open a debate session.

    The session id is minted here rather than taken from the URL. It used to be
    whatever the client put in the path, so anyone could open /ws/<someone
    else's id> and attach to a live session: read its topic and coaching
    replies, push frames and audio into it, and trigger analysis on it. Ids were
    also generated client-side as `user-` plus 7 characters of Math.random(),
    which is neither unguessable nor unique (issue #21).

    This closes the impersonation vector. It is not user authentication -- the
    app has no accounts -- so a session is only as private as its id; see
    docs/ARCHITECTURE.md for what real auth would require.
    """
    session_id = secrets.token_urlsafe(SESSION_ID_BYTES)
    await manager.connect(session_id, websocket)

    try:
        while True:
            data = await receive_or_idle(websocket, session_id)
            if data is None:
                await websocket.close(code=WS_CLOSE_IDLE, reason="idle")
                break

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await manager.send_message(session_id, {
                    "type": "error",
                    "message": "Invalid JSON received",
                })
                continue

            if not isinstance(message, dict):
                await manager.send_message(session_id, {
                    "type": "error",
                    "message": "Expected a JSON object",
                })
                continue

            try:
                await _handle_message(session_id, message)
            except Exception:
                # Keep the connection alive: one malformed message must not tear
                # down a session that is otherwise healthy.
                logger.exception("Error handling %r for session %s", message.get("type"), session_id)
                await manager.send_message(session_id, {
                    "type": "error",
                    "message": "That request could not be processed.",
                })

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error for session %s", session_id)
    finally:
        # One place that tears the session down, whatever ended it: a client
        # disconnect, an idle close, or an error. It used to be duplicated per
        # branch, and the idle path would have been a fourth copy to forget.
        manager.disconnect(session_id, websocket)


# --- Serve frontend static files ---
# In production, the built frontend lives at /app/static (copied by Dockerfile)
# In development, it may be at ../frontend/dist after `npm run build`
STATIC_DIR = os.environ.get("STATIC_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))

if os.path.isdir(STATIC_DIR):
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    STATIC_ROOT = os.path.realpath(STATIC_DIR)
    INDEX_HTML = os.path.join(STATIC_ROOT, "index.html")

    # Catch-all: serve index.html for any non-API, non-WS route (SPA routing)
    @app.get("/{path:path}")
    async def serve_spa(path: str):
        # `path` is attacker-controlled and may contain traversal sequences
        # ("../../backend/.env"), so it is resolved and containment-checked
        # before anything is read off disk.
        candidate = resolve_within(STATIC_ROOT, path)
        if candidate is None:
            logger.warning("Blocked path traversal attempt: %r", path)
            return FileResponse(INDEX_HTML)
        if os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(INDEX_HTML)
else:
    @app.get("/")
    async def root():
        return {
            "message": "Polly AI Debate Coach API",
            "status": "running",
            "note": "Frontend not found. Run 'npm run build' in frontend/ first.",
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
