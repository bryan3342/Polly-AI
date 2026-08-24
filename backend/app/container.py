"""Composition root: the one place that knows the concrete implementations.

Everything else depends on the protocols in `app.services.protocols`. Wiring
lives here so that swapping an implementation — a different STT provider, an
in-memory repository for a test — is a change to this file only, and so
importing the transport layer does not drag in TensorFlow, OpenCV, librosa and
the Gemini SDK.

This module is deliberately the only place that imports all of them.
"""

import logging

from app.api.websocket import ConnectionManager
from app.models.repository import SqlSessionRepository
from app.services.analysis_service import SessionAnalysisService
from app.services.chat_service import ChatService
from app.services.emotion_service import EmotionService
from app.services.prompts import build_feedback_prompt
from app.services.speech_service import SpeechService
from app.services.topic_service import TopicService
from app.services.voice_analysis_service import VoiceAnalysisService

logger = logging.getLogger(__name__)


def build_connection_manager() -> ConnectionManager:
    """Construct the application graph with its real implementations."""
    emotion_service = EmotionService()
    chat_service = ChatService()
    speech_service = SpeechService()
    voice_service = VoiceAnalysisService()
    topic_service = TopicService()

    analysis_service = SessionAnalysisService(
        speech_service=speech_service,
        voice_service=voice_service,
        coach_service=chat_service,
        prompt_builder=build_feedback_prompt,
    )

    logger.info("Application graph constructed.")
    return ConnectionManager(
        emotion_analyzer=emotion_service,
        coach=chat_service,
        topics=topic_service,
        analyzer=analysis_service,
        repository=SqlSessionRepository(),
    )
