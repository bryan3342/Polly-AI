import base64
import logging
from datetime import datetime
from typing import Dict, List, Optional

import cv2
import numpy as np
from deepface import DeepFace

from app.utils.imaging import base64_to_image

logger = logging.getLogger(__name__)

# Fraction of the detected box added on each side before classifying. Haar boxes
# crop tight to the face; expression cues at the brow, jaw and mouth corners sit
# right on that boundary, so a little context measurably helps the classifier.
FACE_MARGIN = 0.18


def empty_result() -> Dict:
    """The canonical 'no face / no analysis' emotion payload.

    Single source of truth: the transport layer and the error paths all build
    this shape, so it lives in one place to keep them from drifting apart.
    """
    return {
        'emotions': None,
        'dominant_emotion': None,
        'confidence': 0.0,
        'face_detected': False,
        'bounding_box': None,
        'timestamp': datetime.now().isoformat(),
    }


class EmotionService:
    def __init__(self):
        self.emotions = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]
        # Load the Haar cascade once and reuse it across frames (frames arrive ~1/sec
        # per client, so re-reading the XML from disk every call was wasteful).
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        logger.info("EmotionService initialized.")

    def warm_up(self) -> bool:
        """Build the emotion model before the first request needs it.

        Constructing it lazily meant the first frame of the first session paid
        for it, which reads to that user as the app being broken. Returns
        whether the model is ready; a failure here is logged and left to the
        per-frame error handling rather than stopping the server, since every
        other feature still works without it.
        """
        try:
            DeepFace.build_model("Emotion", task="facial_attribute")

            # Build the model *and* push one synthetic frame through the real
            # entry point. Constructing the model alone leaves the first genuine
            # frame paying for the graph trace, the Haar cascade's first run and
            # the JPEG decode path — measured at 130ms, which a user experiences
            # as the app stalling on the very first frame of their session.
            blank = np.zeros((64, 64, 3), dtype=np.uint8)
            encoded = cv2.imencode(".jpg", blank)[1].tobytes()
            self.analyze_encoded_frame(
                "data:image/jpeg;base64," + base64.b64encode(encoded).decode()
            )

            logger.info("Emotion model warmed up and ready.")
            return True
        except Exception:
            logger.exception("Could not warm up the emotion model; it will load on first use.")
            return False

    @staticmethod
    def crop_face(frame: np.ndarray, box, margin: float = FACE_MARGIN) -> np.ndarray:
        """Return the face region of `frame`, padded by `margin` and clamped.

        Kept separate from the DeepFace call so the geometry is unit-testable
        without the ML stack.
        """
        x, y, w, h = (int(v) for v in box)
        height, width = frame.shape[:2]

        pad_x = int(w * margin)
        pad_y = int(h * margin)

        x0 = max(0, x - pad_x)
        y0 = max(0, y - pad_y)
        x1 = min(width, x + w + pad_x)
        y1 = min(height, y + h + pad_y)

        crop = frame[y0:y1, x0:x1]
        # A degenerate box (entirely outside the frame) would yield an empty
        # array that DeepFace cannot process; fall back to the whole frame.
        return crop if crop.size else frame

    def analyze_encoded_frame(self, frame_data: str) -> Dict:
        """Decode a base64 data-URL frame and classify it.

        The transport layer used to decode the JPEG itself and fall back to
        `empty_result()` when analysis returned nothing. That made it depend on
        OpenCV and on this module's result shape for something that is entirely
        this service's concern. It now hands over the encoded frame and always
        receives a valid result.
        """
        try:
            frame = base64_to_image(frame_data)
        except Exception:
            logger.exception("Could not decode frame")
            return empty_result()

        return self.analyze_frame(frame) or empty_result()

    def analyze_frame(self, frame: np.ndarray) -> Optional[Dict]:
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))

            if len(faces) == 0:
                return empty_result()

            # detectMultiScale returns boxes in no meaningful order, so picking
            # faces[0] could follow a face in the background between frames.
            # The largest box is the person actually addressing the camera.
            (x, y, w, h) = max(faces, key=lambda box: int(box[2]) * int(box[3]))
            bounding_box = [int(x), int(y), int(w), int(h)]

            # Classify the face, not the room. detector_backend="skip" tells
            # DeepFace to treat its input as an already-cropped face; it was
            # being handed the entire frame, so wall colour, clothing and
            # anything else in shot fed into the emotion scores (issue #26).
            face = self.crop_face(frame, bounding_box)
            face_rgb = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)

            result = DeepFace.analyze(
                face_rgb,
                actions=["emotion"],
                enforce_detection=False,
                detector_backend="skip",
                silent=True
            )

            # DeepFace returns a list of results
            analysis = result[0] if isinstance(result, list) else result

            emotions = analysis.get('emotion', {})
            # Normalize scores to 0-1 range and convert numpy float32 to Python float
            emotion_scores = {k: float(v / 100.0) for k, v in emotions.items()}
            dominant = str(analysis.get('dominant_emotion', 'neutral'))
            confidence = float(emotion_scores.get(dominant, 0.0))

            return {
                'emotions': emotion_scores,
                'dominant_emotion': dominant,
                'confidence': confidence,
                'face_detected': True,
                'bounding_box': bounding_box,
                'timestamp': datetime.now().isoformat()
            }

        except Exception:
            logger.exception("Emotion analysis failed for frame")
            return empty_result()

    def calculate_summary(self, emotion_timeline: List[Dict]) -> Dict:
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
            emotion: float(sum_val / count)
            for emotion, sum_val in emotion_sums.items()
        }

        dominant = max(emotion_averages, key=emotion_averages.get)

        return {
            'averages': emotion_averages,
            'dominant': str(dominant),
            'total': len(emotion_timeline),
            'frames_with_faces': len(valid_entries),
            'confidence': float(emotion_averages.get(dominant, 0)),
            'detections': float(len(valid_entries) / len(emotion_timeline))
        }
