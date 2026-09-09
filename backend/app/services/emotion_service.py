import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.config import config
from app.utils.imaging import base64_to_image

logger = logging.getLogger(__name__)

# Fraction of the detected box added on each side before classifying. Haar boxes
# crop tight to the face; expression cues at the brow, jaw and mouth corners sit
# right on that boundary, so a little context measurably helps the classifier.
FACE_MARGIN = 0.18

# Width of the copy the detector searches. Configurable because the right value
# depends on the camera and how far back the speaker sits; see
# Config.DETECT_WIDTH for the measurements behind the default.
#
# Only the *search* is downscaled. The box is scaled back up and the crop is
# taken from the original frame, so the classifier still receives
# full-resolution pixels.
DETECT_WIDTH = config.DETECT_WIDTH

MODELS = Path(__file__).resolve().parent.parent.parent / ".models"
YUNET_PATH = MODELS / "face_detection_yunet.onnx"
EMOTION_PATH = MODELS / "emotion_ferplus.onnx"

# The order FER+ emits. Not the order this service reports, and not the same set:
# FER+ has a "contempt" class that the rest of the app has no concept of, so it
# is dropped and the remaining seven renormalised.
FERPLUS_CLASSES = ["neutral", "happy", "surprise", "sad",
                   "angry", "disgust", "fear", "contempt"]

EMOTIONS = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]

# Emotions this stack does not actually detect. Measured on 175 labelled faces:
# disgust 2/12 and fear 3/13, and an independent blind labelling pass disputed
# the source label on nearly every one of those images, so even that is
# generous. The scores are still reported, because the shape of the payload is
# part of the contract with the client and the database, but nothing downstream
# should present them as findings. See tests/eval/README.md.
UNRELIABLE = ("disgust", "fear")


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
        self.emotions = list(EMOTIONS)
        # Haar is kept only as the fallback for a machine where the YuNet model
        # file is missing. It detected 159 of 175 labelled faces against YuNet's
        # 174, while costing more per frame (3.8 ms against 2.8 ms), so it is
        # not a tuning choice, just a way to keep working without the download.
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self._detector = None
        self._classifier = None
        # Warm-up runs on a background thread so the server can bind its port
        # immediately, and frames are analysed on worker threads. Both can
        # therefore reach the models at once, and neither cv2.dnn nor
        # FaceDetectorYN promises anything about concurrent construction. The
        # lock makes whoever gets there second wait for the build instead.
        self._model_lock = threading.Lock()
        self._model_ready = False
        logger.info("EmotionService initialized.")

    # -- model loading ------------------------------------------------------

    def warm_up(self) -> bool:
        """Build the models before the first request needs them.

        Constructing them lazily meant the first frame of the first session paid
        for it, which reads to that user as the app being broken. Returns
        whether the classifier is ready; a failure here is logged and left to
        the per-frame error handling rather than stopping the server, since
        every other feature still works without it.

        Safe to call from several threads and safe to call repeatedly: the first
        caller builds while the rest wait, and later calls are free. A failed
        build leaves the service un-warmed so the next frame retries it.
        """
        if self._model_ready:
            return True

        with self._model_lock:
            # Re-checked under the lock: several threads can pass the test above
            # before any of them acquires it.
            if self._model_ready:
                return True
            return self._build_models()

    def _build_models(self) -> bool:
        """Load both networks. Caller must hold `_model_lock`."""
        try:
            self._detector = self._load_detector()
            self._classifier = cv2.dnn.readNetFromONNX(str(EMOTION_PATH))

            # Marked ready *before* the synthetic frame runs: that frame goes
            # through `analyze_frame`, which calls back into `warm_up`. The flag
            # is what stops it recursing into a second build (and deadlocking on
            # this lock, which is not reentrant).
            self._model_ready = True

            # Push one synthetic frame through the real entry point. Loading the
            # networks alone leaves the first genuine frame paying for the first
            # forward pass and the detector's first run.
            self._classify(np.zeros((64, 64, 3), dtype=np.uint8))

            logger.info("Emotion models warmed up and ready.")
            return True
        except Exception:
            # Cleared again so the next frame retries rather than trusting a
            # half-built stack.
            self._model_ready = False
            logger.exception(
                "Could not load the emotion models; emotion detection is "
                "unavailable. Run scripts/fetch_models.py to download them. "
                "Everything else still works."
            )
            return False

    def _load_detector(self):
        """YuNet if its model is present, otherwise None to mean 'use Haar'."""
        if not YUNET_PATH.exists():
            logger.warning(
                "%s is missing, falling back to the Haar cascade. That detects "
                "roughly 91%% of faces against YuNet's 99%%; run "
                "scripts/fetch_models.py to fix it.", YUNET_PATH.name,
            )
            return None
        return cv2.FaceDetectorYN.create(str(YUNET_PATH), "", (320, 320), 0.6, 0.3, 5000)

    # -- geometry -----------------------------------------------------------

    @staticmethod
    def crop_face(frame: np.ndarray, box, margin: float = FACE_MARGIN) -> np.ndarray:
        """Return the face region of `frame`, padded by `margin` and clamped.

        Kept separate from the classifier call so the geometry is unit-testable
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
        # array the classifier cannot process; fall back to the whole frame.
        return crop if crop.size else frame

    @staticmethod
    def align(frame: np.ndarray, box, landmarks) -> Tuple[np.ndarray, List[int]]:
        """Rotate `frame` so the speaker's eyes are level, and follow the box.

        The classifier was trained on roughly upright faces, so a head tilted
        against the back of a chair is being asked a question outside what it
        was taught. Rotating about the midpoint between the eyes costs one
        warpAffine and no second detection pass, because the box centre can be
        pushed through the same matrix rather than searched for again.
        """
        right_eye, left_eye = landmarks[0], landmarks[1]
        dy = float(left_eye[1] - right_eye[1])
        dx = float(left_eye[0] - right_eye[0])
        angle = np.degrees(np.arctan2(dy, dx))

        centre = ((right_eye + left_eye) / 2).astype(float)
        matrix = cv2.getRotationMatrix2D((float(centre[0]), float(centre[1])), angle, 1.0)

        height, width = frame.shape[:2]
        rotated = cv2.warpAffine(
            frame, matrix, (width, height),
            flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE,
        )

        x, y, w, h = (int(v) for v in box)
        box_centre = np.array([x + w / 2.0, y + h / 2.0, 1.0])
        moved = matrix @ box_centre
        return rotated, [int(moved[0] - w / 2), int(moved[1] - h / 2), w, h]

    def detect_faces(self, frame: np.ndarray,
                     search_width: Optional[int] = None) -> List[List[int]]:
        """Locate faces, optionally searching a downscaled copy for speed.

        Returns boxes in the *original* frame's coordinates, so callers never
        see the downscaling. Landmarks, when the detector produces them, are
        available from `detect_faces_with_landmarks`; this narrower signature is
        what the transport layer draws its overlay from.
        """
        return [box for box, _ in self.detect_faces_with_landmarks(frame, search_width)]

    def detect_faces_with_landmarks(self, frame: np.ndarray,
                                    search_width: Optional[int] = None):
        """Faces as `(box, landmarks)`; landmarks is None under the Haar fallback.

        `search_width` of 0 (the default configuration) searches the frame as
        captured, which is what a machine with CPU to spare should do: detection
        accuracy is the thing this app is for. A fractional-CPU host sets a
        width; see Config.DETECT_WIDTH for the measurements.
        """
        if search_width is None:
            search_width = DETECT_WIDTH

        height, width = frame.shape[:2]
        # `search_width <= 0` disables downscaling entirely. Guarding it here
        # rather than at the call site keeps a zero from becoming a zero-sized
        # resize, which OpenCV raises on.
        scale = search_width / width if 0 < search_width < width else 1.0

        if scale < 1.0:
            search = cv2.resize(
                frame, (int(width * scale), int(height * scale)),
                interpolation=cv2.INTER_AREA,
            )
        else:
            search = frame

        if self._detector is not None:
            found = self._detect_yunet(search)
        else:
            found = self._detect_haar(search)

        # Back to full-resolution coordinates. The overlay the client draws and
        # the crop the classifier sees are both in those terms.
        out = []
        for box, landmarks in found:
            box = [int(v / scale) for v in box]
            if landmarks is not None:
                landmarks = landmarks / scale
            out.append((box, landmarks))
        return out

    def _detect_yunet(self, frame: np.ndarray):
        height, width = frame.shape[:2]
        self._detector.setInputSize((width, height))
        _, faces = self._detector.detect(frame)
        if faces is None:
            return []
        # Columns 0-3 are the box, 4-13 are five landmarks as x/y pairs:
        # right eye, left eye, nose tip, right mouth corner, left mouth corner.
        return [([int(f[0]), int(f[1]), int(f[2]), int(f[3])],
                 np.array(f[4:14], dtype=float).reshape(5, 2)) for f in faces]

    def _detect_haar(self, frame: np.ndarray):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
        return [([int(v) for v in box], None) for box in faces]

    # -- classification -----------------------------------------------------

    def _classify(self, face: np.ndarray) -> np.ndarray:
        """Emotion probabilities for an already-cropped face, in EMOTIONS order.

        Averaged with the mirror image. The classifier is not symmetric, so a
        face lit from one side scores differently from its reflection, and
        averaging the two is a cheap way to stop that asymmetry deciding the
        answer. Measured at +2 points of accuracy for ~3 ms.
        """
        return (self._forward(face) + self._forward(cv2.flip(face, 1))) / 2

    def _forward(self, face: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (64, 64)).astype(np.float32)

        self._classifier.setInput(gray.reshape(1, 1, 64, 64))
        logits = self._classifier.forward().flatten()

        # FER+ emits logits, not probabilities.
        exp = np.exp(logits - logits.max())
        probabilities = exp / exp.sum()

        by_name = dict(zip(FERPLUS_CLASSES, probabilities))
        scores = np.array([by_name[name] for name in EMOTIONS], dtype=float)
        # Renormalised because dropping "contempt" leaves the rest summing to
        # less than one, and the client shows these as percentages.
        total = scores.sum()
        return scores / total if total else scores

    # -- entry points -------------------------------------------------------

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
        # A frame can arrive while the background warm-up is still running, or
        # after it failed. Building here too keeps that from racing: this either
        # returns immediately or waits for the in-flight build to finish.
        if not self.warm_up():
            return empty_result()

        try:
            faces = self.detect_faces_with_landmarks(frame)

            if not faces:
                return empty_result()

            # Boxes come back in no meaningful order, so faces[0] could follow a
            # face in the background between frames. The largest box is the
            # person actually addressing the camera.
            bounding_box, landmarks = max(faces, key=lambda f: f[0][2] * f[0][3])

            # The box reported to the client stays in the coordinates of the
            # frame it actually sent, so the overlay still lines up; only the
            # pixels handed to the classifier are rotated.
            reported_box = bounding_box
            if landmarks is not None:
                frame, bounding_box = self.align(frame, bounding_box, landmarks)

            # Classify the face, not the room: the classifier is given the crop
            # rather than the frame, so wall colour, clothing and anything else
            # in shot stay out of the scores (issue #26).
            face = self.crop_face(frame, bounding_box)

            scores = self._classify(face)
            emotion_scores = {name: float(value)
                              for name, value in zip(EMOTIONS, scores)}
            dominant = EMOTIONS[int(scores.argmax())]

            return {
                'emotions': emotion_scores,
                'dominant_emotion': str(dominant),
                'confidence': float(emotion_scores[dominant]),
                'face_detected': True,
                'bounding_box': reported_box,
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
