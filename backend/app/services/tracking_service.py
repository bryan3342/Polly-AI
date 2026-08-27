"""Everything measured from a single video frame, decoded once.

Emotion needs the face; gesture metrics need the hands. Both start from the
same JPEG, and decoding it twice would cost a few milliseconds per frame per
analyser for no benefit -- the same reason `DecodedRecording` exists on the
audio side.

So this owns the decode and hands the resulting array to each analyser. It
presents the same two methods the transport layer already depends on
(`analyze_encoded_frame`, `calculate_summary`), so adding hand tracking changed
nothing about how frames are routed.
"""

import logging
from typing import Dict, List

from app.services.emotion_service import EmotionService, empty_result as empty_emotion
from app.services.gesture_service import (
    GestureService,
    empty_result as empty_gesture,
)
from app.utils.imaging import base64_to_image

logger = logging.getLogger(__name__)


class TrackingService:
    """Face, emotion, hands and fingers from one frame."""

    def __init__(self, emotion: EmotionService, gesture: GestureService):
        self._emotion = emotion
        self._gesture = gesture

    def warm_up(self) -> bool:
        """Build both models. Returns whether emotion -- the one the score
        depends on most -- came up; hand tracking degrades on its own."""
        emotion_ready = self._emotion.warm_up()
        self._gesture.warm_up()
        return emotion_ready

    def analyze_encoded_frame(self, frame_data: str) -> Dict:
        """Decode one base64 data-URL frame and measure everything in it.

        Always returns a valid result. A frame that cannot be decoded is not a
        session-ending event -- the next one arrives in a tenth of a second.
        """
        try:
            frame = base64_to_image(frame_data)
        except Exception:
            logger.exception("Could not decode frame")
            return {**empty_emotion(), **empty_gesture()}

        emotion = self._emotion.analyze_frame(frame) or empty_emotion()
        gesture = self._gesture.analyze_frame(frame)

        # The frame's own dimensions travel with the result so the client can
        # scale the face box, which is in pixels, to whatever size it is
        # displaying the video at. Hand landmarks are already normalised, and
        # the skeleton's bone list is sent once at connect rather than here.
        height, width = frame.shape[:2]
        return {
            **emotion,
            **gesture,
            "frame_width": int(width),
            "frame_height": int(height),
        }

    def calculate_summary(self, timeline: List[Dict]) -> Dict:
        """Aggregate a session. Emotion and gesture summarise independently, so
        one being unmeasurable never suppresses the other."""
        summary = self._emotion.calculate_summary(timeline) or {}
        summary["gesture_summary"] = self._gesture.calculate_summary(timeline)
        return summary
