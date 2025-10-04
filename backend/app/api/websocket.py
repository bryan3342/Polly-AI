from fastapi import WebSocket, WebSocketDisconnect
import json
import base64
import numpy as np
import cv2
from PIL import Image
from io import BytesIO
from typing import Dict
from datetime import datetime
from app.services.emotion_service import EmotionService
from app.services.chat_service import ChatService

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_data: Dict[str, dict] = {}
    
        self.emotion_service = EmotionService()
        self.chat_service = ChatService()

    async def connect(self,session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.session_data[session_id] = {
            "start_time": datetime.now(),
            "frames_count": 0,
            "emotions": [],
            "faces_detected": 0,
            "audio_chunks": 0,
            "chat-history": []
        }
        print(f"Session {session_id} connected.")
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            del self.session_data[session_id]
        print(f"Session {session_id} disconnected.")
    
    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)
        
    def base64_to_image(self, base64_str: str) -> np.ndarray:

        # Remove data URL prefix if present
        if ',' in base64_str:
            base64_str = base64_str.split(',')[1]
        
        # Decode base64 string to bytes
        img_data = base64.b64decode(base64_str)

        # Convert to PIL image
        image = Image.open(BytesIO(img_data))

        # Convert to numpy array (RGB)
        img_array = np.array(image)

        # Convert RGB to BGR for OpenCV
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        return img_bgr

    async def process_frame(self, session_id: str, frame_data: str, timestamp: float):
        """Process a video frame for emotion detection"""
        try:
            # Convert to OpenCV format
            frame = self.base64_to_image(frame_data)
            
            # Analyze emotions
            result = self.emotion_service.analyze_frame(frame)
            
            # Store in session
            if session_id in self.session_data:
                self.session_data[session_id]["frame_count"] += 1
                if result.get("face_detected"):
                    self.session_data[session_id]["emotion_timeline"].append(result)
            
            # Send result back to client
            await self.send_message(session_id, {
                "type": "emotion_update",
                "data": result,
                "frame_number": self.session_data[session_id].get("frame_count", 0)
            })
            
            return result
            
        except Exception as e:
            print(f"Error processing frame: {str(e)}")
            await self.send_message(session_id, {
                "type": "error",
                "message": f"Frame processing error: {str(e)}"
            })
            return None
        
    async def process_chat_message(self, session_id: str, prompt: str):

        # Get emotional context
        summary = self.get_session_summary(session_id)

        # Get GPT Response
        gpt_text = await self.chat_service.get_response(session_id, prompt, summary)

        # Store user and GPT message in session history
        if session_id in self.session_data:
            self.session_data[session_id]["chat_history"].append({"role": "user", "content": prompt})
            self.session_data[session_id]["chat_history"].append({"role": "assistant", "content": gpt_text})

        # Send GPT response back to the client
        await self.send_message(session_id, {
            "type": "chat_response",
            "message": gpt_text,
            "timestamp": datetime.now().isoformat()
        })

        print(f"Chat message processed for {session_id}. Response sent")


    def get_session_summary(self, session_id: str) -> dict:
        """Get emotion summary for a session"""
        if session_id not in self.session_data:
            return {}
        
        emotion_timeline = self.session_data[session_id]["emotion_timeline"]
        summary = self.emotion_service.calculate_summary(emotion_timeline)
        
        return {
            "session_duration": (datetime.now() - self.session_data[session_id]["start_time"]).total_seconds(),
            "total_frames": self.session_data[session_id]["frame_count"],
            "emotion_summary": summary
        }

manager = ConnectionManager()
