from fastapi import WebSocket, WebSocketDisconnect
import json
import base64
import numpy as np
import cv2
from PIL import Image
from io import BytesIO
from typing import Dict
import asyncio
from datetime import datetime

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_data: Dict[str, dict] = {}
    
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

manager = ConnectionManager()
