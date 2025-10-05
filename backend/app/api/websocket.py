from fastapi import WebSocket, WebSocketDisconnect
import json
import base64
import numpy as np
import cv2
from PIL import Image
from io import BytesIO
from typing import Dict
from datetime import datetime
from backend.app.services.emotion_service import EmotionService
from backend.app.services.chat_service import ChatService
from backend.app.services.speech_service import SpeechService
from backend.app.services.topic_service import TopicService
from backend.app.services.voice_analysis_service import VoiceAnalysisService

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_data: Dict[str, dict] = {}
    
        self.emotion_service = EmotionService()
        self.chat_service = ChatService()
        self.speech_service = SpeechService()
        self.topic_service = TopicService()
        self.voice_service = VoiceAnalysisService()

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        
        # Get a random debate topic
        topic = self.topic_service.get_random_topic()
        
        self.session_data[session_id] = {
            "start_time": datetime.now(),
            "frame_count": 0,
            "emotions": [],
            "faces_detected": 0,
            "audio_chunks": [],
            "chat_history": [],
            "topic": topic,
            "recording_state": "idle",  # idle, recording, processing
            "recording_start_time": None,
            "audio_data": bytearray()
        }
        
        print(f"Session {session_id} connected.")

        # Send a greeting message with the topic
        greeting = await self.chat_service.get_gpt_response(
            session_id,
            f"Greet the user as Polly AI, their debate coach. Present them with this debate topic: '{topic.get('topic')}'. Ask them to take a stance (for or against) and give them a brief speech (30-60 seconds) defending their position. Be encouraging and explain they can either type or use the microphone to record their response. Make sure to end with letting them know to start when they're ready.",
            None
        )

        await self.send_message(session_id, {
            "type": "chat_response",
            "message": greeting,
            "timestamp": datetime.now().isoformat()
        })
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            del self.session_data[session_id]
        print(f"Session {session_id} disconnected.")
    
    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)
        
    def base64_to_image(self, base64_str: str) -> np.ndarray:
        if ',' in base64_str:
            base64_str = base64_str.split(',')[1]
        
        img_data = base64.b64decode(base64_str)
        image = Image.open(BytesIO(img_data))
        img_array = np.array(image)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        return img_bgr

    async def process_frame(self, session_id: str, frame_data: str, timestamp: float):
        try:
            frame = self.base64_to_image(frame_data)
            result = self.emotion_service.analyze_frame(frame)
            
            # ADD THIS CHECK
            if result is None:
                result = {
                    'emotions': None,
                    'dominant_emotion': None,
                    'confidence': 0.0,
                    'face_detected': False,
                    'bounding_box': None,
                    'timestamp': datetime.now().isoformat()
                }
            
            if session_id in self.session_data:
                self.session_data[session_id]["frame_count"] += 1
                if result.get("face_detected"):
                    self.session_data[session_id]["emotions"].append(result)
            
            await self.send_message(session_id, {
                "type": "emotion_update",
                "data": result,
                "frame_number": self.session_data[session_id].get("frame_count", 0)
            })
            
            return result
            
        except Exception as e:
            print(f"Error processing frame: {str(e)}")
            error_result = {
                'emotions': None,
                'dominant_emotion': None,
                'confidence': 0.0,
                'face_detected': False,
                'bounding_box': None,
                'timestamp': datetime.now().isoformat()
            }
            await self.send_message(session_id, {
                "type": "emotion_update",
                "data": error_result,
                "frame_number": self.session_data[session_id].get("frame_count", 0)
            })
        return error_result
    
    async def start_recording(self, session_id: str):
        """Start recording debate session"""
        if session_id in self.session_data:
            self.session_data[session_id]["recording_state"] = "recording"
            self.session_data[session_id]["recording_start_time"] = datetime.now()
            self.session_data[session_id]["audio_data"] = bytearray()
            self.session_data[session_id]["emotions"] = []  # Reset emotions for this recording
            
            await self.send_message(session_id, {
                "type": "recording_started",
                "timestamp": datetime.now().isoformat()
            })
            print(f"Recording started for session {session_id}")
    
    async def stop_recording(self, session_id: str):
        """Stop recording and process the debate"""
        if session_id not in self.session_data:
            return
        
        session = self.session_data[session_id]
        session["recording_state"] = "processing"
        
        await self.send_message(session_id, {
            "type": "recording_stopped",
            "message": "Processing your debate..."
        })
        
        # Calculate duration
        duration = (datetime.now() - session["recording_start_time"]).total_seconds()
        
        # Process audio
        audio_bytes = bytes(session["audio_data"])
        transcript_data = await self.speech_service.transcribe_audio(audio_bytes)
        speech_analysis = self.speech_service.analyze_speech_patterns(transcript_data)
        
        # Voice analysis
        voice_analysis = self.voice_service.analyze_audio(audio_bytes)
        tone_description = self.voice_service.get_tone_description(voice_analysis)
        
        # Emotion summary
        emotion_summary = self.get_session_summary(session_id)
        
        # Generate comprehensive feedback
        feedback = await self.generate_feedback(
            session_id,
            transcript_data,
            speech_analysis,
            voice_analysis,
            tone_description,
            emotion_summary,
            duration
        )
        
        # Save to database
        self.save_session_to_db(
            session_id,
            transcript_data,
            speech_analysis,
            voice_analysis,
            emotion_summary,
            feedback,
            duration
        )
        
        # Send results to client
        await self.send_message(session_id, {
            "type": "analysis_complete",
            "results": {
                "transcript": transcript_data.get("text", ""),
                "speech_analysis": speech_analysis,
                "voice_analysis": voice_analysis,
                "tone_description": tone_description,
                "emotion_summary": emotion_summary,
                "feedback": feedback,
                "duration": duration
            }
        })
        
        session["recording_state"] = "complete"
        print(f"Analysis complete for session {session_id}")

    async def transcribe_and_send(self, session_id: str, audio_data: str):
        """Transcribe audio and send back as text"""
        try:
            # Decode base64 audio data
            if ',' in audio_data:
                audio_data = audio_data.split(',')[1]
            
            audio_bytes = base64.b64decode(audio_data)
            
            # Transcribe the audio
            transcript_data = await self.speech_service.transcribe_audio(audio_bytes)
            transcript_text = transcript_data.get('text', 'Could not transcribe audio')
            
            # Send transcription back to client
            await self.send_message(session_id, {
                "type": "transcription_complete",
                "transcript": transcript_text,
                "timestamp": datetime.now().isoformat()
            })
            
            print(f"Audio transcribed for session {session_id}: {transcript_text[:50]}...")
            
        except Exception as e:
            print(f"Error transcribing audio: {str(e)}")
            await self.send_message(session_id, {
                "type": "transcription_complete",
                "transcript": "[Error transcribing audio]",
                "timestamp": datetime.now().isoformat()
            })


    async def process_audio_chunk(self, session_id: str, audio_data: str):
        """Receive and store audio chunks during recording"""
        if session_id not in self.session_data:
            return
        
        session = self.session_data[session_id]
        if session["recording_state"] != "recording":
            return
        
        try:
            # Decode base64 audio data
            if ',' in audio_data:
                audio_data = audio_data.split(',')[1]
            
            audio_bytes = base64.b64decode(audio_data)
            session["audio_data"].extend(audio_bytes)
            
        except Exception as e:
            print(f"Error processing audio chunk: {str(e)}")

    async def transcribe_and_send(self, session_id: str, audio_data: str):
        """Transcribe audio and send back as text"""
        try:
            # Decode base64 audio data
            if ',' in audio_data:
                audio_data = audio_data.split(',')[1]
            
            audio_bytes = base64.b64decode(audio_data)
            
            # Transcribe the audio
            transcript_data = await self.speech_service.transcribe_audio(audio_bytes)
            transcript_text = transcript_data.get('text', 'Could not transcribe audio')
            
            # Send transcription back to client
            await self.send_message(session_id, {
                "type": "transcription_complete",
                "transcript": transcript_text,
                "timestamp": datetime.now().isoformat()
            })
            
            print(f"Audio transcribed for session {session_id}: {transcript_text[:50]}...")
            
        except Exception as e:
            print(f"Error transcribing audio: {str(e)}")
            await self.send_message(session_id, {
                "type": "transcription_complete",
                "transcript": "[Error transcribing audio]",
                "timestamp": datetime.now().isoformat()
            })

    
    async def generate_feedback(self, session_id: str, transcript_data: Dict, 
                                speech_analysis: Dict, voice_analysis: Dict,
                                tone_description: str, emotion_summary: Dict, 
                                duration: float) -> str:
        """Generate comprehensive AI feedback"""
        session = self.session_data[session_id]
        topic = session["topic"]
        
        prompt = f"""
        Analyze this debate practice session and provide constructive feedback.
        
        DEBATE TOPIC: {topic.get('topic')}
        DURATION: {duration:.1f} seconds
        
        TRANSCRIPT:
        {transcript_data.get('text', 'No transcript available')}
        
        SPEECH METRICS:
        - Word count: {speech_analysis.get('word_count', 0)}
        - Speaking pace: {speech_analysis.get('words_per_minute', 0)} words/minute
        - Filler words: {speech_analysis.get('filler_word_count', 0)} ({speech_analysis.get('filler_percentage', 0)}%)
        - Average pause duration: {speech_analysis.get('average_pause_duration', 0)} seconds
        
        VOICE ANALYSIS:
        - Tone: {tone_description}
        - Confidence score: {voice_analysis.get('confidence_score', 0)}/100
        
        EMOTIONAL STATE:
        - Dominant emotion: {emotion_summary.get('emotion_summary', {}).get('dominant', 'neutral')}
        - Detection rate: {emotion_summary.get('emotion_summary', {}).get('detections', 0):.1%}
        
        Please provide:
        1. Overall assessment (2-3 sentences)
        2. Strengths (2-3 specific points)
        3. Areas for improvement (2-3 specific points)
        4. Actionable tips for next practice (3-4 concrete suggestions)
        
        Keep feedback constructive, specific, and encouraging.
        """
        
        return await self.chat_service.get_gpt_response(session_id, prompt, emotion_summary)
    
    async def process_chat_message(self, session_id: str, prompt: str):
        """Handle chat messages"""
        summary = self.get_session_summary(session_id)
        gpt_text = await self.chat_service.get_gpt_response(session_id, prompt, summary)

        if session_id in self.session_data:
            self.session_data[session_id]["chat_history"].append({"role": "user", "content": prompt})
            self.session_data[session_id]["chat_history"].append({"role": "assistant", "content": gpt_text})

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
        
        emotion_timeline = self.session_data[session_id]["emotions"]
        summary = self.emotion_service.calculate_summary(emotion_timeline)
        
        return {
            "session_duration": (datetime.now() - self.session_data[session_id]["start_time"]).total_seconds(),
            "total_frames": self.session_data[session_id]["frame_count"],
            "emotion_summary": summary
        }
    
    def save_session_to_db(self, session_id: str, transcript_data: Dict, 
                          speech_analysis: Dict, voice_analysis: Dict,
                          emotion_summary: Dict, feedback: str, duration: float):
        """Save session data to database"""
        try:
            session = self.session_data[session_id]
            topic = session["topic"]
            
            session_data = {
                "session_id": session_id,
                "topic_id": topic.get("id"),
                "topic_text": topic.get("topic"),
                "duration": duration,
                "transcript": transcript_data.get("text", ""),
                "word_count": speech_analysis.get("word_count", 0),
                "words_per_minute": speech_analysis.get("words_per_minute", 0),
                "voice_analysis": voice_analysis,
                "confidence_score": voice_analysis.get("confidence_score", 0),
                "emotion_summary": emotion_summary.get("emotion_summary", {}),
                "dominant_emotion": emotion_summary.get("emotion_summary", {}).get("dominant", "neutral"),
                "ai_feedback": feedback,
                "overall_score": self._calculate_overall_score(speech_analysis, voice_analysis, emotion_summary)
            }
            
            SessionModel.create_session(session_data)
            print(f"Session {session_id} saved to database")
            
        except Exception as e:
            print(f"Error saving session to database: {str(e)}")
    
    def _calculate_overall_score(self, speech_analysis: Dict, voice_analysis: Dict, emotion_summary: Dict) -> float:
        """Calculate overall performance score (0-100)"""
        scores = []
        
        # Speech score (0-100)
        wpm = speech_analysis.get("words_per_minute", 0)
        if 120 <= wpm <= 160:  # Ideal range
            speech_score = 100
        elif 100 <= wpm <= 180:
            speech_score = 80
        else:
            speech_score = 60
        
        # Penalize for filler words
        filler_pct = speech_analysis.get("filler_percentage", 0)
        speech_score -= min(20, filler_pct * 2)
        scores.append(max(0, speech_score))
        
        # Confidence score (already 0-100)
        scores.append(voice_analysis.get("confidence_score", 50))
        
        # Emotion score - prefer confident/neutral emotions
        emotion_data = emotion_summary.get("emotion_summary", {})
        dominant = emotion_data.get("dominant", "neutral")
        emotion_score = 70  # baseline
        if dominant in ["happy", "neutral"]:
            emotion_score = 85
        elif dominant in ["surprise"]:
            emotion_score = 75
        elif dominant in ["sad", "angry", "fear"]:
            emotion_score = 50
        scores.append(emotion_score)
        
        # Average all scores
        return round(sum(scores) / len(scores), 1)

manager = ConnectionManager()