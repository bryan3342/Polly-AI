import json
import logging
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.websocket import manager
from app.config import config
from app.database import init_db
from app.utils.paths import resolve_within

# Logging is configured in app/__init__.py, before these imports execute.
logger = logging.getLogger(__name__)

app = FastAPI(title="Polly AI Debate Coach")

init_db()

# Explicit origin allow-list. `allow_origins=["*"]` cannot be combined with
# allow_credentials=True -- browsers reject that combination outright.
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
    else:
        logger.warning("Unknown message type %r from session %s", message_type, session_id)
        await manager.send_message(session_id, {
            "type": "error",
            "message": f"Unknown message type: {message_type}",
        })


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()

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
        manager.disconnect(session_id, websocket)
    except Exception:
        logger.exception("WebSocket error for session %s", session_id)
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
