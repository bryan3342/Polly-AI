from fastapi import WebSocket, WebSocketDisconnect
import json
import base64
import numpy as np
import cv2
from PIL import Image
from io import BytesIO
from typing import Dict
from datetime import datetime

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_data: Dict[str, dict] = {}
    
        from app.services.emotion_service import EmotionService
        self.emotion_service = EmotionService()

    async def connect(self,session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.session_data[session_id] = {
            "start_time": datetime.now(),
            "frames_count": 0,
            "emotions": [],
            "faces_detected": 0,
            "audio_chunks": 0
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
                self.session_data[session_id]["emotion_timeline"].append(result)
            
            # Send result back to client
            await self.send_message(session_id, {
                "type": "emotion_update",
                "data": result,
                "frame_number": self.session_data[session_id]["frame_count"]
            })
            
            return result
            
        except Exception as e:
            print(f"⚠️ Error processing frame: {str(e)}")
            await self.send_message(session_id, {
                "type": "error",
                "message": f"Frame processing error: {str(e)}"
            })
            return None
        
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
