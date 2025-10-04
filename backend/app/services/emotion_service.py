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

            # DeepFace expects RGB images, convert BGR (OpenCV format) to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Analyze emotions
            # NOTE: DeepFace will try to detect a face internally
            result = DeepFace.analyze (
                frame_rgb,
                actions=["emotion"],
                enforce_detection=False, # If no face detected, no errors
                detector_backend="opencv",
                silent=True # Suppress verbose output
            )

            # DeepFace returns a list of results, even for single image
            if isinstance(result, list) and len(result) > 0:
                result = result[0]

            # Initialize bounding box variable
            bounding_box = None
            
            # --- NEW: Extract Bounding Box Coordinates ---
            # DeepFace stores the coordinates in the 'region' key as a dictionary {'x', 'y', 'w', 'h'}
            if result and 'region' in result:
                region = result['region']
                # Convert the dictionary into the list format [x, y, w, h] that the frontend expects
                bounding_box = [region['x'], region['y'], region['w'], region['h']]
            # ---------------------------------------------


            if result and 'emotion' in result:
                emotions = result['emotion']
                dominant_emotion = result['dominant_emotion']

                # Normalize emotion scores to 0-1 range
                total = sum(emotions.values())
                normalized_emotions = {
                    emotion : score / total for emotion, score in emotions.items()
                }
                
                dominant_confidence = normalized_emotions[dominant_emotion]

                # Only accept if confidence above threshold
                MIN_CONFIDENCE = 0.05

                if dominant_confidence < MIN_CONFIDENCE:
                    dominant_emotion = "neutral"
                    print(f"Low confidence ({dominant_confidence:.2%}), defaulting to neutral")

            
                return {
                    'emotions' : normalized_emotions,
                    'dominant_emotion' : dominant_emotion,
                    'confidence' : normalized_emotions.get(dominant_emotion, 0),
                    'face_detected' : True,
                    'bounding_box' : bounding_box, # <-- ADDED
                    'timestamp' : datetime.now().isoformat()
                }
            else:
                return {
                    'emotions' : None,
                    'dominant_emotion' : None,
                    'confidence' : 0.0,
                    'face_detected' : False,
                    'bounding_box' : None, # <-- ADDED
                    'timestamp' : datetime.now().isoformat()
                }
        
        except Exception as e:
            print(f"Error in emotion analysis: {str(e)}")
            return {
                'emotions' : None,
                'dominant_emotion' : None,
                'confidence' : 0.0,
                'face_detected' : False,
                'bounding_box' : None, # <-- ADDED
                'timestamp' : datetime.now().isoformat()
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
