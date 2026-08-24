"""WebSocket transport layer.

This module owns connection lifecycle and message fan-out only. Image decoding,
JSON sanitization, domain scoring, and prompt construction live in their own
modules so this layer stays focused on transport.
"""

import asyncio
import base64
import logging
from datetime import datetime
from typing import Dict, Optional

from fastapi import WebSocket

from app.config import config
from app.models.session import SessionModel
from app.services import emotion_service as emotion_module
from app.services import scoring_service
from app.services.chat_service import ChatService
from app.services.emotion_service import EmotionService
from app.services.speech_service import SpeechService
from app.services.topic_service import TopicService
from app.services.voice_analysis_service import VoiceAnalysisService
from app.utils.imaging import base64_to_image
from app.utils.serialization import sanitize

logger = logging.getLogger(__name__)


def _build_feedback_prompt(topic: Dict, duration: float, transcript_data: Dict,
                           speech_analysis: Dict, tone_description: str,
                           voice_analysis: Dict, emotion_summary: Dict) -> str:
    """Compose the post-session analysis prompt sent to the coaching model."""
    emotions = (emotion_summary or {}).get("emotion_summary", {}) or {}
    confidence = (voice_analysis or {}).get("confidence_score")
    detections = emotions.get("detections")

    caveat = ""
    if transcript_data.get("is_mock"):
        caveat = (
            "\nNOTE: Speech-to-text is not enabled, so the transcript and the metrics "
            "derived from it are placeholders. Do not comment on the wording of the "
            "transcript; focus your feedback on vocal delivery and composure.\n"
        )

    return f"""
        Analyze this debate practice session and provide constructive feedback.
        {caveat}
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
        - Confidence score: {'unavailable' if confidence is None else f'{confidence}/100'}

        EMOTIONAL STATE:
        - Dominant emotion: {emotions.get('dominant', 'not detected')}
        - Detection rate: {'unavailable' if detections is None else f'{detections:.1%}'}

        Please provide:
        1. Overall assessment (2-3 sentences)
        2. Strengths (2-3 specific points)
        3. Areas for improvement (2-3 specific points)
        4. Actionable tips for next practice (3-4 concrete suggestions)

        Keep feedback constructive, specific, and encouraging.
        """


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_data: Dict[str, dict] = {}
        # Bounds concurrent emotion inference across all sessions; see
        # config.MAX_CONCURRENT_INFERENCES.
        self._inference_slots = asyncio.Semaphore(config.MAX_CONCURRENT_INFERENCES)

        self.emotion_service = EmotionService()
        self.chat_service = ChatService()
        self.speech_service = SpeechService()
        self.topic_service = TopicService()
        self.voice_service = VoiceAnalysisService()

    # ── session state ────────────────────────────────────────────────
    def get_session(self, session_id: str) -> Optional[dict]:
        """Return live session state, or None if the session is gone.

        Every handler must go through this rather than indexing session_data
        directly: a client can disconnect between messages, and an unguarded
        lookup would raise and tear down an unrelated live connection.
        """
        return self.session_data.get(session_id)

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()

        # A reused session_id would otherwise overwrite the live session's state
        # and let the older connection's disconnect() delete it out from under
        # the newer one. Close the previous socket and start clean.
        existing = self.active_connections.get(session_id)
        if existing is not None:
            logger.warning("Session %s reconnected with an id already in use; closing the older socket.", session_id)
            try:
                await existing.close(code=1012)  # service restart / superseded
            except Exception:
                logger.debug("Could not close superseded socket for %s", session_id, exc_info=True)

        self.active_connections[session_id] = websocket

        topic = self.topic_service.get_random_topic()

        self.session_data[session_id] = {
            "start_time": datetime.now(),
            "frame_count": 0,
            "emotions": [],
            "topic": topic,
            "recording_state": "idle",  # idle, recording, processing, complete
            "recording_start_time": None,
            "audio_data": bytearray(),
            "audio_truncated": False,
        }

        logger.info("Session %s connected.", session_id)

        # The client no longer chooses its own id, so it is told what it got.
        # Useful for correlating client-side logs with server logs; it is not a
        # credential the client needs to send back.
        await self.send_message(session_id, {
            "type": "session_assigned",
            "session_id": session_id,
        })

        await self.send_message(session_id, {
            "type": "topic_assigned",
            "topic": topic,
        })

        welcome = (
            "Welcome to Polly AI — your personal debate coach!\n\n"
            "Here's how it works:\n"
            "1. I've assigned you a debate topic above. Hit the refresh button if you'd like a different one.\n"
            "2. Click **Record** when you're ready to practice your argument.\n"
            "3. While you speak, I'll track your facial expressions in real time.\n"
            "4. Click **Stop** when you're done — I'll analyze your speech, vocal tone, and emotions, "
            "then give you a detailed performance report.\n\n"
            "You can also type here anytime to ask me for debate tips, counter-arguments, or coaching advice. Let's get started!"
        )
        await self.send_message(session_id, {
            "type": "chat_response",
            "message": welcome,
            "timestamp": datetime.now().isoformat(),
        })

    def disconnect(self, session_id: str, websocket: WebSocket = None):
        """Tear down a session.

        When `websocket` is given, the entry is only removed if it is still the
        active socket for that id, so a superseded connection closing later
        cannot evict the live one.
        """
        current = self.active_connections.get(session_id)
        if websocket is not None and current is not None and current is not websocket:
            logger.info("Ignoring disconnect from superseded socket for session %s", session_id)
            return

        self.active_connections.pop(session_id, None)
        self.session_data.pop(session_id, None)
        self.chat_service.clear_history(session_id)
        logger.info("Session %s disconnected.", session_id)

    async def send_message(self, session_id: str, message: dict):
        websocket = self.active_connections.get(session_id)
        if websocket is None:
            return
        await websocket.send_json(sanitize(message))

    # ── frame handling ───────────────────────────────────────────────
    def _analyze_frame_blocking(self, frame_data: str) -> Dict:
        """JPEG decode + DeepFace inference. Runs on a worker thread."""
        frame = base64_to_image(frame_data)
        return self.emotion_service.analyze_frame(frame) or emotion_module.empty_result()

    async def process_frame(self, session_id: str, frame_data: str, timestamp: float):
        try:
            # Base64/JPEG decoding and DeepFace inference are both CPU-bound and
            # synchronous. Run directly in this coroutine they blocked the whole
            # event loop for every connected session on every frame, at one
            # frame per second per client.
            #
            # The semaphore bounds how many inferences run at once: the
            # underlying TensorFlow graph is not safely reentrant, and letting
            # N clients each start an inference would thrash CPU and memory on
            # a shared-CPU instance. Requests beyond the limit wait their turn
            # instead of piling onto the loop.
            async with self._inference_slots:
                result = await asyncio.to_thread(self._analyze_frame_blocking, frame_data)
        except Exception:
            logger.exception("Error processing frame for session %s", session_id)
            result = emotion_module.empty_result()

        session = self.get_session(session_id)
        frame_count = 0
        if session is not None:
            session["frame_count"] += 1
            frame_count = session["frame_count"]
            if result.get("face_detected"):
                emotions = session["emotions"]
                emotions.append(result)
                # Bound the timeline so a long-lived session cannot grow the heap
                # without limit; the summary only needs a representative window.
                if len(emotions) > config.MAX_EMOTION_FRAMES:
                    del emotions[:-config.MAX_EMOTION_FRAMES]

        await self.send_message(session_id, {
            "type": "emotion_update",
            "data": result,
            "frame_number": frame_count,
        })

    # ── recording lifecycle ──────────────────────────────────────────
    async def start_recording(self, session_id: str):
        """Start recording debate session"""
        session = self.get_session(session_id)
        if session is None:
            return

        session.update({
            "recording_state": "recording",
            "recording_start_time": datetime.now(),
            "audio_data": bytearray(),
            "audio_truncated": False,
            "emotions": [],  # Reset emotions for this recording
        })

        await self.send_message(session_id, {
            "type": "recording_started",
            "timestamp": datetime.now().isoformat(),
        })
        logger.info("Recording started for session %s", session_id)

    async def process_audio_chunk(self, session_id: str, audio_data: str):
        """Receive and store audio chunks during recording"""
        session = self.get_session(session_id)
        if session is None or session["recording_state"] != "recording":
            return

        try:
            if ',' in audio_data:
                audio_data = audio_data.split(',')[1]
            audio_bytes = base64.b64decode(audio_data)
        except Exception:
            logger.exception("Error decoding audio chunk for session %s", session_id)
            return

        buffer = session["audio_data"]
        remaining = config.MAX_AUDIO_BYTES - len(buffer)
        if remaining <= 0:
            if not session["audio_truncated"]:
                logger.warning("Audio buffer cap reached for session %s; dropping further audio.", session_id)
                session["audio_truncated"] = True
            return

        buffer.extend(audio_bytes[:remaining])
        if len(audio_bytes) > remaining:
            session["audio_truncated"] = True

    async def stop_recording(self, session_id: str):
        """Stop recording and process the debate"""
        session = self.get_session(session_id)
        if session is None:
            return

        # Ignore a stop that arrives without an active recording (e.g. stop before
        # start). recording_start_time is None until start_recording runs, so
        # computing duration below would raise TypeError and kill the WS loop.
        if session["recording_state"] != "recording" or session.get("recording_start_time") is None:
            await self.send_message(session_id, {
                "type": "recording_stopped",
                "message": "No active recording to stop.",
            })
            return

        session["recording_state"] = "processing"

        await self.send_message(session_id, {
            "type": "recording_stopped",
            "message": "Processing your debate...",
        })

        duration = (datetime.now() - session["recording_start_time"]).total_seconds()
        audio_bytes = bytes(session["audio_data"])

        transcript_data = await self.speech_service.transcribe_audio(audio_bytes)
        speech_analysis = self.speech_service.analyze_speech_patterns(transcript_data)

        # librosa feature extraction (plus the ffmpeg decode it now performs) is
        # seconds of synchronous CPU work on a long recording; keep it off the
        # loop so other sessions keep receiving frames while it runs.
        voice_analysis = await asyncio.to_thread(self.voice_service.analyze_audio, audio_bytes)
        tone_description = self.voice_service.get_tone_description(voice_analysis)

        emotion_summary = self.get_session_summary(session_id)

        feedback = await self.generate_feedback(
            session_id, duration, transcript_data, speech_analysis,
            tone_description, voice_analysis, emotion_summary,
        )

        overall_score = scoring_service.calculate_overall_score(
            speech_analysis, voice_analysis, emotion_summary,
        )

        self.save_session_to_db(
            session_id, transcript_data, speech_analysis, voice_analysis,
            emotion_summary, feedback, duration, overall_score,
        )

        await self.send_message(session_id, {
            "type": "analysis_complete",
            "results": {
                "transcript": transcript_data.get("text", ""),
                "transcript_is_mock": bool(transcript_data.get("is_mock")),
                "transcript_error": transcript_data.get("error"),
                "speech_analysis": speech_analysis,
                "voice_analysis": voice_analysis,
                "voice_analysis_degraded": bool(voice_analysis.get("degraded")),
                "tone_description": tone_description,
                "emotion_summary": emotion_summary,
                "feedback": feedback,
                "duration": duration,
                "overall_score": overall_score,
                "audio_truncated": session.get("audio_truncated", False),
            },
        })

        # The session may have been torn down while the analysis was awaiting.
        session = self.get_session(session_id)
        if session is not None:
            session["recording_state"] = "complete"
        logger.info("Analysis complete for session %s", session_id)

    # ── chat + summaries ─────────────────────────────────────────────
    async def generate_feedback(self, session_id: str, duration: float, transcript_data: Dict,
                                speech_analysis: Dict, tone_description: str,
                                voice_analysis: Dict, emotion_summary: Dict) -> str:
        """Generate comprehensive AI feedback"""
        session = self.get_session(session_id)
        topic = (session or {}).get("topic", {})

        prompt = _build_feedback_prompt(
            topic, duration, transcript_data, speech_analysis,
            tone_description, voice_analysis, emotion_summary,
        )
        # record_history=False: this machine-generated prompt should not become
        # part of the user-visible conversation context.
        return await self.chat_service.get_coach_response(
            session_id, prompt, emotion_summary, record_history=False,
        )

    async def process_chat_message(self, session_id: str, prompt: str):
        """Handle chat messages"""
        if not prompt:
            await self.send_message(session_id, {
                "type": "error",
                "message": "Empty chat message.",
            })
            return

        summary = self.get_session_summary(session_id)
        # ChatService owns conversation history; storing a second copy on the
        # session would be a duplicate source of truth.
        reply = await self.chat_service.get_coach_response(session_id, prompt, summary)

        await self.send_message(session_id, {
            "type": "chat_response",
            "message": reply,
            "timestamp": datetime.now().isoformat(),
        })
        logger.debug("Chat message processed for session %s", session_id)

    async def assign_new_topic(self, session_id: str) -> None:
        """Assign a fresh random topic to a live session."""
        session = self.get_session(session_id)
        if session is None:
            return

        new_topic = self.topic_service.get_random_topic()
        session["topic"] = new_topic
        await self.send_message(session_id, {
            "type": "topic_assigned",
            "topic": new_topic,
        })

    def get_session_summary(self, session_id: str) -> dict:
        """Get emotion summary for a session"""
        session = self.get_session(session_id)
        if session is None:
            return {}

        summary = self.emotion_service.calculate_summary(session["emotions"])

        return {
            "session_duration": (datetime.now() - session["start_time"]).total_seconds(),
            "total_frames": session["frame_count"],
            "emotion_summary": summary,
        }

    def save_session_to_db(self, session_id: str, transcript_data: Dict,
                           speech_analysis: Dict, voice_analysis: Dict,
                           emotion_summary: Dict, feedback: str, duration: float,
                           overall_score: Optional[float]):
        """Save session data to database"""
        session = self.get_session(session_id)
        if session is None:
            logger.warning("Session %s vanished before its results could be saved.", session_id)
            return

        topic = session.get("topic", {})
        emotions = (emotion_summary or {}).get("emotion_summary", {}) or {}

        record = {
            "session_id": session_id,
            "topic_id": topic.get("id"),
            "topic_text": topic.get("topic"),
            "duration": duration,
            # Placeholder transcripts are not stored as if they were real speech.
            "transcript": "" if transcript_data.get("is_mock") else transcript_data.get("text", ""),
            "word_count": speech_analysis.get("word_count", 0),
            "words_per_minute": speech_analysis.get("words_per_minute", 0),
            "voice_analysis": voice_analysis,
            "confidence_score": voice_analysis.get("confidence_score"),
            "emotion_summary": emotions,
            "dominant_emotion": emotions.get("dominant"),
            "ai_feedback": feedback,
            "overall_score": overall_score,
        }

        if SessionModel.create_session(sanitize(record)) is not None:
            logger.info("Session %s saved to database", session_id)


manager = ConnectionManager()
