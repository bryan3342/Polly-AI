from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.websocket import manager
from app.services.topic_service import TopicService
from app.database import init_db
import json
import os

app = FastAPI(title="Polly AI Debate Coach")

# Initialize database
init_db()

topic_service = TopicService()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "ok"}

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
                    "message": "Invalid JSON received"
                })
                continue

            message_type = message.get("type")

            if message_type == "frame":
                await manager.process_frame(
                    session_id,
                    message.get("data"),
                    message.get("timestamp")
                )

            elif message_type == "start_recording":
                await manager.start_recording(session_id)

            elif message_type == "stop_recording":
                await manager.stop_recording(session_id)

            elif message_type == "audio_complete":
                await manager.process_audio_chunk(
                    session_id,
                    message.get("data")
                )

            elif message_type == "chat":
                await manager.process_chat_message(
                    session_id,
                    message.get("message")
                )

            elif message_type == "request_new_topic":
                new_topic = topic_service.get_random_topic()
                manager.session_data[session_id]["topic"] = new_topic
                await manager.send_message(session_id, {
                    "type": "topic_assigned",
                    "topic": new_topic
                })

            else:
                print(f"Unknown message type: {message_type}")

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        print(f"Client {session_id} disconnected")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        manager.disconnect(session_id)

# --- Serve frontend static files ---
# In production, the built frontend lives at /app/static (copied by Dockerfile)
# In development, it may be at ../frontend/dist after `npm run build`
STATIC_DIR = os.environ.get("STATIC_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))

if os.path.isdir(STATIC_DIR):
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    # Catch-all: serve index.html for any non-API, non-WS route (SPA routing)
    @app.get("/{path:path}")
    async def serve_spa(path: str):
        file_path = os.path.join(STATIC_DIR, path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
else:
    @app.get("/")
    async def root():
        return {"message": "Polly AI Debate Coach API", "status": "running", "note": "Frontend not found. Run 'npm run build' in frontend/ first."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
