from deepface import DeepFace
import cv2
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime

class EmotionService:
    def __init__(self):

        self.emotions = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]
        print("Emotion Detection Model Loading")
    
    def analyze_frame(self, frame: np.ndarray):
        try:
            # Use Haar Cascade for face detection (like test code)
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
            
            if len(faces) == 0:
                return {
                    'emotions': None,
                    'dominant_emotion': None,
                    'confidence': 0.0,
                    'face_detected': False,
                    'bounding_box': None,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Get first face
            (x, y, w, h) = faces[0]
            bounding_box = [int(x), int(y), int(w), int(h)]
            
            # Now analyze emotions on the detected face region
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            result = DeepFace.analyze(
                frame_rgb,
                actions=["emotion"],
                enforce_detection=False,
                detector_backend="skip",  # Skip DeepFace's face detection
                silent=True
            )
            
        except Exception as e:
            print(f"Error in emotion analysis: {str(e)}")
            import traceback
            traceback.print_exc()  # ADD THIS to see the full error
            return {
                'emotions': None,
                'dominant_emotion': None,
                'confidence': 0.0,
                'face_detected': False,
                'bounding_box': None,
                'timestamp': datetime.now().isoformat()
        }
    
    def calculate_summary(self, emotion_timeline: List[Dict]):

        if not emotion_timeline:
            return {}
    
        valid_entries = [
            entry for entry in emotion_timeline
            if entry.get('face_detected') and entry.get('emotions')
        ]

        if not valid_entries:
            return {}

        emotion_sums = {}
        for entry in valid_entries:
            for emotion, score in entry['emotions'].items():
                emotion_sums[emotion] = emotion_sums.get(emotion, 0) + score

        count = len(valid_entries)
        emotion_averages = {
            emotion: sum_val / count
            for emotion, sum_val in emotion_sums.items()
        }

        dominant = max(emotion_averages, key=emotion_averages.get)

        return {
            'averages'  : emotion_averages,
            'dominant'  : dominant,
            'total' : len(emotion_timeline),
            'frames_with_faces' : len(valid_entries),
            'confidence' : emotion_averages.get(dominant, 0),
            'detections' : len(valid_entries) / len(emotion_timeline)
        }
