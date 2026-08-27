"""Hand and finger tracking, for the gesture half of a delivery.

Why not OpenCV: OpenCV detects faces well -- a Haar cascade does that job in
this app already -- but it ships no hand or finger model. The cascades that
exist for palms and fists are unreliable and give a bounding box, not fingers,
so they cannot tell an open palm from a fist or a pointed finger. MediaPipe's
hand landmarker returns 21 3D points per hand, which is what "track fingers"
actually requires. OpenCV still does the decoding and the geometry around it.

Pinned below 1.0: mediapipe 1.x aborts the process on macOS with
"Check failed: service_ Service is unavailable" from inside its Metal helper,
which takes the whole server down rather than raising something catchable.
0.10.35 runs the same model on CPU in 5.4 ms per 720p frame.

Landmarks are reported normalised to 0-1 against the frame, so the client can
draw them over a video element of any size without knowing the capture
resolution.
"""

import logging
import os
import threading
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Index of each landmark in MediaPipe's hand model, for the few we reason about.
WRIST = 0
FINGERTIPS = (4, 8, 12, 16, 20)          # thumb, index, middle, ring, pinky

# Pairs of landmark indices that form the hand skeleton, so the client can draw
# bones rather than a cloud of unrelated dots.
HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),           # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),           # index
    (5, 9), (9, 10), (10, 11), (11, 12),      # middle
    (9, 13), (13, 14), (14, 15), (15, 16),    # ring
    (13, 17), (17, 18), (18, 19), (19, 20),   # pinky
    (0, 17),                                  # palm base
)

DEFAULT_MODEL_PATH = os.path.join(".models", "hand_landmarker.task")


def empty_result() -> Dict:
    """The canonical 'no hands' payload.

    A single shape for every path -- no model, no hands, failed inference -- so
    the client never has to distinguish them, and the transport layer cannot
    drift from what this service actually returns.
    """
    return {"hands": [], "hands_detected": False, "hand_count": 0}


class GestureService:
    """Locates hands and fingers in a frame."""

    def __init__(self, model_path: Optional[str] = None, max_hands: int = 2):
        self.model_path = model_path or os.environ.get(
            "HAND_LANDMARK_MODEL", DEFAULT_MODEL_PATH
        )
        self.max_hands = max_hands
        self._landmarker = None
        # Built lazily on a background thread, and read from worker threads
        # handling frames; MediaPipe's graph is not safe to enter concurrently.
        self._lock = threading.Lock()
        self._ready = False
        self._unavailable_reason: Optional[str] = None
        logger.info("GestureService initialized (model=%s).", self.model_path)

    # ── model lifecycle ──────────────────────────────────────────────
    def warm_up(self) -> bool:
        """Build the landmarker before the first frame needs it.

        Returns whether hand tracking is available. A failure here is logged and
        left alone rather than raised: every other measurement in this app still
        works without hands, and the report says which parts were measured.
        """
        if self._ready:
            return True

        with self._lock:
            if self._ready:
                return True
            return self._build()

    def _build(self) -> bool:
        """Construct the landmarker. Caller must hold `_lock`."""
        if not os.path.exists(self.model_path):
            self._unavailable_reason = (
                f"hand model not found at {self.model_path}; run "
                f"scripts/fetch_models.py"
            )
            logger.warning("Hand tracking unavailable: %s", self._unavailable_reason)
            return False

        try:
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions, vision

            self._mp = mp
            options = vision.HandLandmarkerOptions(
                base_options=BaseOptions(
                    model_asset_path=self.model_path,
                    # CPU explicitly: the GPU delegate is what fails on macOS,
                    # and 5.4 ms a frame leaves no reason to want it.
                    delegate=BaseOptions.Delegate.CPU,
                ),
                # IMAGE rather than VIDEO. VIDEO mode wants monotonic timestamps
                # per stream, and frames here arrive from any number of sessions
                # on shared worker threads, where "the previous frame" is not a
                # meaningful idea.
                running_mode=vision.RunningMode.IMAGE,
                num_hands=self.max_hands,
                min_hand_detection_confidence=0.5,
                min_hand_presence_confidence=0.5,
            )
            self._landmarker = vision.HandLandmarker.create_from_options(options)
            self._ready = True
            logger.info("Hand landmarker ready.")
            return True
        except Exception as exc:
            self._unavailable_reason = str(exc)
            logger.exception("Could not build the hand landmarker")
            return False

    @property
    def available(self) -> bool:
        return self._ready

    # ── per-frame ────────────────────────────────────────────────────
    def analyze_frame(self, frame: np.ndarray) -> Dict:
        """Locate hands in a BGR frame. Always returns a valid result."""
        if not self._ready and not self.warm_up():
            return empty_result()

        try:
            import cv2

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = self._mp.Image(
                image_format=self._mp.ImageFormat.SRGB, data=rgb
            )
            # Serialised: one MediaPipe graph, entered from several frame
            # workers, is not safe concurrently.
            with self._lock:
                result = self._landmarker.detect(image)
        except Exception:
            logger.exception("Hand tracking failed for a frame")
            return empty_result()

        hands = []
        for index, landmarks in enumerate(result.hand_landmarks or []):
            handedness = "unknown"
            if result.handedness and index < len(result.handedness):
                entry = result.handedness[index]
                if entry:
                    handedness = entry[0].category_name

            # Rounded to three places: enough for drawing at any sane display
            # size, and it keeps a 21-point hand from bloating every frame
            # message with float noise.
            points = [[round(p.x, 3), round(p.y, 3)] for p in landmarks]
            hands.append({
                "handedness": handedness,
                "landmarks": points,
                "fingertips": [points[i] for i in FINGERTIPS if i < len(points)],
            })

        return {
            "hands": hands,
            "hands_detected": bool(hands),
            "hand_count": len(hands),
        }

    # ── session aggregate ────────────────────────────────────────────
    @staticmethod
    def calculate_summary(timeline: List[Dict]) -> Dict:
        """Summarise a session's hand tracking into gesture metrics.

        `timeline` is the per-frame results, in order. Everything here is
        measured off those frames -- nothing is inferred when hands were never
        seen, because "hands not visible" and "speaker kept still" are different
        things and only the first is knowable from this data.
        """
        frames = len(timeline)
        if not frames:
            return {"frames": 0, "hands_visible_ratio": None}

        visible = [f for f in timeline if f.get("hands_detected")]
        visible_ratio = len(visible) / frames

        # Movement: how far the wrists travel between consecutive frames where
        # a hand was seen, in frame-widths. A still speaker scores near zero, a
        # constantly moving one high; both extremes read badly to an audience.
        movement = []
        previous = None
        for frame in timeline:
            hands = frame.get("hands") or []
            if not hands:
                previous = None            # a gap is not a movement
                continue
            wrist = hands[0]["landmarks"][WRIST]
            if previous is not None:
                movement.append(
                    ((wrist[0] - previous[0]) ** 2 + (wrist[1] - previous[1]) ** 2) ** 0.5
                )
            previous = wrist

        return {
            "frames": frames,
            "frames_with_hands": len(visible),
            "hands_visible_ratio": round(visible_ratio, 3),
            "average_hands_visible": round(
                sum(f.get("hand_count", 0) for f in timeline) / frames, 2
            ),
            "movement_per_frame": round(sum(movement) / len(movement), 4) if movement else None,
        }
