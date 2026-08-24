"""Interfaces the transport layer depends on.

The WebSocket layer used to import the concrete services directly, which meant
importing it pulled in TensorFlow, OpenCV, librosa and the Gemini SDK. Tests
that wanted to exercise transport had to inject fake modules into `sys.modules`
before importing anything — a strong signal that the dependency ran the wrong
way.

These protocols are structural (`typing.Protocol`), so the existing services
satisfy them without inheriting anything, and a test fake satisfies them by
having the right methods. Nothing here imports a heavy dependency.
"""

from typing import Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class EmotionAnalyzer(Protocol):
    """Facial emotion from encoded video frames."""

    def analyze_encoded_frame(self, frame_data: str) -> Dict:
        """Classify one base64 data-URL frame. Always returns a valid result."""
        ...

    def calculate_summary(self, emotion_timeline: List[Dict]) -> Dict:
        """Aggregate a session's frame results."""
        ...


@runtime_checkable
class SpeechAnalyzer(Protocol):
    """Transcription and speaking-pattern metrics."""

    async def transcribe_audio(self, recording) -> Dict: ...

    def analyze_speech_patterns(self, transcript_data: Dict) -> Dict: ...


@runtime_checkable
class VoiceAnalyzer(Protocol):
    """Vocal tone measurement."""

    def analyze_audio(self, recording) -> Dict: ...

    def get_tone_description(self, analysis: Dict) -> str: ...


@runtime_checkable
class CoachingService(Protocol):
    """Conversational coaching, with per-session history."""

    async def get_coach_response(self, session_id: str, prompt: str,
                                 emotion_summary: Dict = None,
                                 record_history: bool = True) -> str: ...

    def clear_history(self, session_id: str) -> None: ...


@runtime_checkable
class TopicProvider(Protocol):
    """Debate topic assignment."""

    def get_random_topic(self) -> Dict: ...


@runtime_checkable
class SessionRepository(Protocol):
    """Persistence for finished sessions.

    Behind an interface so the transport layer neither knows nor cares that the
    store is SQLite, and so tests need no database.
    """

    def save(self, record: Dict) -> bool:
        """Persist one session record. Returns whether it was written."""
        ...


@runtime_checkable
class SessionAnalyzer(Protocol):
    """Turns a finished recording into a report."""

    async def analyze(self, request) -> object: ...


class EmotionResult:
    """The canonical 'nothing detected' emotion payload.

    Lives here rather than in the DeepFace-backed service so the transport layer
    and tests can reference the shape without importing the ML stack.
    """

    @staticmethod
    def empty(timestamp: Optional[str] = None) -> Dict:
        from datetime import datetime

        return {
            'emotions': None,
            'dominant_emotion': None,
            'confidence': 0.0,
            'face_detected': False,
            'bounding_box': None,
            'timestamp': timestamp or datetime.now().isoformat(),
        }
