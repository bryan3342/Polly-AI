from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.api.websocket import manager
from app.database import init_db
import json

app = FastAPI(title="Polly AI Debate Coach")

# Initialize database
init_db()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Polly AI Debate Coach API", "status": "running"}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            message_type = message.get("type")
            
            if message_type == "frame":
                # Process video frame for emotion detection
                await manager.process_frame(
                    session_id,
                    message.get("data"),
                    message.get("timestamp")
                )
            
            elif message_type == "start_recording":
                # Start debate recording
                await manager.start_recording(session_id)
            
            elif message_type == "stop_recording":
                # Stop recording and process
                await manager.stop_recording(session_id)
            
            elif message_type == "audio_complete":
                # Receive complete audio data
                await manager.process_audio_chunk(
                    session_id,
                    message.get("data")
                )
            
            elif message_type == "chat":
                # Process chat message
                await manager.process_chat_message(
                    session_id,
                    message.get("message")
                )
            
            elif message_type == "request_new_topic":
                # Send new random topic
                from app.services.topic_service import TopicService
                topic_service = TopicService()
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)