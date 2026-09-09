"""Composition root: the one place that knows the concrete implementations.

Everything else depends on the protocols in `app.services.protocols`. Wiring
lives here so that swapping an implementation, a different STT provider, an
in-memory repository for a test, is a change to this file only, and so
importing the transport layer does not drag in OpenCV, librosa, mediapipe and
the Gemini SDK.

This module is deliberately the only place that imports all of them.
"""

import logging
from typing import Callable, NamedTuple

from app.api.websocket import ConnectionManager
from app.config import config
from app.models.repository import SqlSessionRepository
from app.services.analysis_service import SessionAnalysisService
from app.services.chat_service import ChatService
from app.services.emotion_service import EmotionService
from app.services.gesture_service import GestureService
from app.services.model_check import check_configured_models
from app.services.prompts import build_feedback_prompt
from app.services.speech_service import SpeechService
from app.services.topic_service import TopicService
from app.services.tracking_service import TrackingService
from app.services.voice_analysis_service import VoiceAnalysisService

logger = logging.getLogger(__name__)


class Application(NamedTuple):
    """The wired graph, plus the startup work that must not block it.

    `warm_up` is handed back rather than called during construction because the
    two have different timing requirements: the graph must exist before the app
    can serve anything, while warming the emotion model only has to finish
    before the first frame. Keeping them separate lets `app.main` bind its port
    first and warm up behind the health check.
    """

    manager: ConnectionManager
    warm_up: Callable[[], bool]


def build_application() -> Application:
    """Construct the application graph with its real implementations."""
    emotion_service = EmotionService()
    gesture_service = GestureService()
    # One decode per frame, shared by both analysers.
    tracking_service = TrackingService(emotion_service, gesture_service)
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
    manager = ConnectionManager(
        emotion_analyzer=tracking_service,
        coach=chat_service,
        topics=topic_service,
        analyzer=analysis_service,
        repository=SqlSessionRepository(),
    )

    def warm_up() -> bool:
        """The startup work that must not hold up the port bind.

        Two unrelated things, deliberately together: both are slow, neither is
        needed before the server can accept a connection, and both are better
        discovered at startup than by a user mid-session.
        """
        ready = tracking_service.warm_up()
        # Names expire. Checked here so a retired model is an error in the log
        # at startup, rather than a coach that mysteriously "has trouble
        # responding" once someone is already recording.
        check_configured_models(
            config.GEMINI_API_KEY,
            [config.TRANSCRIPTION_MODEL, config.CHAT_MODEL],
        )
        return ready

    # Building the emotion models used to happen right here, during import.
    # That made uvicorn's port bind wait for them to load, spending a host's
    # startup budget before the health check could even be answered, and Cloud
    # Run caps container startup at 4 minutes. The caller now schedules this in
    # the background instead.
    return Application(manager=manager, warm_up=warm_up)
