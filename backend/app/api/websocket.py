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
from app.services.analysis_service import AnalysisRequest
from app.services.protocols import (
    CoachingService,
    EmotionAnalyzer,
    EmotionResult,
    SessionAnalyzer,
    SessionRepository,
    TopicProvider,
)
from app.utils.serialization import sanitize

logger = logging.getLogger(__name__)


# Close code sent when a connection is reaped for inactivity. 4000-4999 is the
# range reserved for application use, so it cannot collide with a protocol code.
# The client recognises this one and reconnects when the user comes back,
# instead of treating it as an error worth showing.
WS_CLOSE_IDLE = 4000


async def receive_or_idle(websocket, session_id: str, timeout: Optional[float] = None):
    """Await the next client message, or None if the connection went idle.

    Returning None rather than raising keeps the caller's loop readable, and
    keeps "the user left" distinct from "the connection broke" -- they want
    different close codes and different client behaviour.

    Lives here rather than beside the route because it is a transport concern,
    and because `app.main` cannot be imported without the whole ML stack, which
    would put this out of reach of the unit suite.
    """
    if timeout is None:
        timeout = config.WS_IDLE_TIMEOUT_SECONDS

    # Disabled. On an always-on host there is no per-request billing to save,
    # and reaping a session there only costs the user their topic and history.
    if timeout <= 0:
        return await websocket.receive_text()

    try:
        return await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.info("Closing session %s after %.0fs idle", session_id, timeout)
        return None


class ConnectionManager:
    """WebSocket connection lifecycle and message fan-out.

    Collaborators are injected rather than constructed here: this layer is about
    transport, and building the analysis stack was both a second responsibility
    and the reason importing this module pulled in TensorFlow, OpenCV, librosa
    and the Gemini SDK. See `app.container` for the wiring.
    """

    def __init__(self,
                 emotion_analyzer: EmotionAnalyzer,
                 coach: CoachingService,
                 topics: TopicProvider,
                 analyzer: SessionAnalyzer,
                 repository: SessionRepository,
                 max_concurrent_inferences: Optional[int] = None):
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_data: Dict[str, dict] = {}

        self.emotion_service = emotion_analyzer
        self.chat_service = coach
        self.topic_service = topics
        self.analysis_service = analyzer
        self.repository = repository

        # Bounds concurrent emotion inference across all sessions; see
        # config.MAX_CONCURRENT_INFERENCES.
        limit = max_concurrent_inferences or config.MAX_CONCURRENT_INFERENCES
        self._inference_slots = asyncio.Semaphore(limit)

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
            "frames_dropped": 0,
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

        # Capture settings travel with the session rather than being compiled
        # into the client. The right frame rate is a property of the machine
        # running inference -- a laptop and a fractional-CPU instance differ by
        # more than an order of magnitude -- and only this side knows which one
        # it is. It also means moving between them needs no frontend rebuild.
        await self.send_message(session_id, {
            "type": "capture_settings",
            "frame_interval_ms": config.FRAME_INTERVAL_MS,
            "idle_frame_interval_ms": config.IDLE_FRAME_INTERVAL_MS,
            "jpeg_quality": config.FRAME_JPEG_QUALITY,
            "capture_width": config.CAPTURE_WIDTH,
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
        """Frame decode + inference. Runs on a worker thread.

        Both steps belong to the analyzer; this layer only decides *where* the
        work runs, not how a frame becomes an emotion.
        """
        return self.emotion_service.analyze_encoded_frame(frame_data)

    async def process_frame(self, session_id: str, frame_data: str, timestamp: float):
        # Drop this frame if every inference slot is busy, rather than waiting
        # for one.
        #
        # Frames arrive on a fixed clock -- once a second while recording -- but
        # inference takes however long the host's CPU takes. Where that is
        # slower than the arrival rate, awaiting the semaphore queued the
        # backlog: latency grew without bound, memory with it, and every frame
        # that finally ran described a moment that had long passed. On a small
        # shared CPU that is not an edge case, it is the normal state.
        #
        # Dropping is the honest response. Emotion tracking is a sample of a
        # continuous signal, so a sparser sample is a real answer, where a
        # minutes-stale one is not. What the user sees is a readout that updates
        # more slowly on a slow host, instead of one that falls progressively
        # further behind for the rest of the session.
        if self._inference_slots.locked():
            session = self.get_session(session_id)
            if session is not None:
                session["frames_dropped"] += 1
            return

        try:
            # Base64/JPEG decoding and DeepFace inference are both CPU-bound and
            # synchronous. Run directly in this coroutine they blocked the whole
            # event loop for every connected session on every frame, at one
            # frame per second per client.
            #
            # The semaphore bounds how many inferences run at once: the
            # underlying TensorFlow graph is not safely reentrant, and letting
            # N clients each start an inference would thrash CPU and memory on
            # a shared-CPU instance.
            async with self._inference_slots:
                result = await asyncio.to_thread(self._analyze_frame_blocking, frame_data)
        except Exception:
            logger.exception("Error processing frame for session %s", session_id)
            result = EmotionResult.empty()

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

        request = AnalysisRequest(
            session_id=session_id,
            audio=bytes(session["audio_data"]),
            duration=duration,
            topic=session.get("topic", {}),
            emotion_summary=self.get_session_summary(session_id),
            audio_truncated=session.get("audio_truncated", False),
        )

        analysis = await self.analysis_service.analyze(request)

        self.save_session_to_db(session_id, analysis)

        await self.send_message(session_id, {
            "type": "analysis_complete",
            "results": analysis.to_payload(),
        })

        # The session may have been torn down while the analysis was awaiting.
        session = self.get_session(session_id)
        if session is not None:
            session["recording_state"] = "complete"
        logger.info("Analysis complete for session %s", session_id)

    # ── chat + summaries ─────────────────────────────────────────────
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

    def save_session_to_db(self, session_id: str, analysis) -> None:
        """Persist a finished analysis.

        The row layout lives on SessionAnalysis.to_record so the wire payload and
        the stored record are derived from one object and cannot drift apart.
        """
        session = self.get_session(session_id)
        if session is None:
            logger.warning("Session %s vanished before its results could be saved.", session_id)
            return

        self.repository.save(analysis.to_record(session_id, session.get("topic", {})))
