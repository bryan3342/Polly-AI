from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.config import config
from app.api.websocket import manager
import uuid
import json

app = FastAPI(title = "Polly Debate AI - Real-Time Analysis")

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins = config.CORS_ORIGINS,
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "mode": "real-time"}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            message_type = message.get("type")

            if message_type == "frame":
                # Handling video frame
                frame_data = message.get("data")
                timestamp = message.get("timestamp")

                # Receipt of frame being received
                await manager.send_message(session_id, {
                    "type" : "frame_received",
                    "timestamp" : timestamp
                })

            elif message_type == "audio":
                # Handling audio chunk
                audio_data = message.get("data")

                await manager.send_message(session_id, {
                    "type" : "audio_received",
                    "timestamp" : message.get("timestamp")
                })
            
            elif message_type == "end_session":
                # Handling session end
                await manager.send_message(session_id, {
                    "type" : "session_ended",
                    "message" : "Session Completed",
                    "timestamp" : message.get("timestamp")
                })
                break
    except WebSocketDisconnect:
        manager.disconnect(session_id)
        print(f"Session {session_id} disconnected.")
    except Exception as e:
        print(f"Error in session {session_id}: {e}")
        manager.disconnect(session_id)