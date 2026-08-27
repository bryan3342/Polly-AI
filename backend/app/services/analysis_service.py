"""Post-recording analysis: turning one recording into a report.

This is the domain work that happens when a user stops recording, transcribe,
measure the voice, summarise emotion, score, and ask the coach for feedback.

It lives here rather than in the WebSocket handler because none of it is about
transport. The handler previously ran the whole sequence inline, which meant the
rules for what gets analysed and how the result is shaped could only be
exercised by standing up a WebSocket connection.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from app.services import scoring_service
from app.utils.audio import AudioDecodeError, DecodedRecording

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnalysisRequest:
    """Everything needed to analyse one recording.

    A value object rather than a long parameter list: the caller assembles it
    from session state, and the analyser needs no access to that state.
    """

    session_id: str
    audio: bytes
    duration: float
    topic: Dict = field(default_factory=dict)
    emotion_summary: Dict = field(default_factory=dict)
    audio_truncated: bool = False


@dataclass(frozen=True)
class SessionAnalysis:
    """The finished report for one recording.

    Named fields rather than a free-form dict so the wire payload, the database
    record and the feedback prompt cannot drift apart: they are all derived
    from this one object.
    """

    duration: float
    transcript: str
    transcript_is_mock: bool
    transcript_error: Optional[str]
    speech_analysis: Dict
    voice_analysis: Dict
    tone_description: str
    emotion_summary: Dict
    feedback: str
    overall_score: Optional[float]
    audio_truncated: bool

    @property
    def voice_analysis_degraded(self) -> bool:
        return bool(self.voice_analysis.get("degraded"))

    @property
    def dominant_emotion(self) -> Optional[str]:
        return self._emotions.get("dominant")

    @property
    def _emotions(self) -> Dict:
        return (self.emotion_summary or {}).get("emotion_summary", {}) or {}

    def to_payload(self) -> Dict:
        """The `analysis_complete` results object sent to the client."""
        return {
            "transcript": self.transcript,
            "transcript_is_mock": self.transcript_is_mock,
            "transcript_error": self.transcript_error,
            "speech_analysis": self.speech_analysis,
            "voice_analysis": self.voice_analysis,
            "voice_analysis_degraded": self.voice_analysis_degraded,
            "tone_description": self.tone_description,
            "emotion_summary": self.emotion_summary,
            "feedback": self.feedback,
            "duration": self.duration,
            "overall_score": self.overall_score,
            "audio_truncated": self.audio_truncated,
        }

    def to_record(self, session_id: str, topic: Dict) -> Dict:
        """The row persisted for this session."""
        return {
            "session_id": session_id,
            "topic_id": (topic or {}).get("id"),
            "topic_text": (topic or {}).get("topic"),
            "duration": self.duration,
            # A transcript we could not produce is never stored as if it were
            # the user's actual speech.
            "transcript": "" if self.transcript_is_mock else self.transcript,
            "word_count": self.speech_analysis.get("word_count", 0),
            "words_per_minute": self.speech_analysis.get("words_per_minute", 0),
            "voice_analysis": self.voice_analysis,
            "confidence_score": self.voice_analysis.get("confidence_score"),
            "emotion_summary": self._emotions,
            "dominant_emotion": self.dominant_emotion,
            "ai_feedback": self.feedback,
            "overall_score": self.overall_score,
        }


class SessionAnalysisService:
    """Runs the analysis sequence for a finished recording.

    Collaborators are injected so the sequence can be tested against fakes;
    nothing here imports the ML stack.
    """

    def __init__(self, speech_service, voice_service, coach_service, prompt_builder):
        self._speech = speech_service
        self._voice = voice_service
        self._coach = coach_service
        self._build_prompt = prompt_builder

    async def analyze(self, request: AnalysisRequest) -> SessionAnalysis:
        # Decode once here rather than in each analyser: both need PCM, and
        # decoding twice meant two ffmpeg subprocesses per recording and two
        # places that had to agree on the decode settings.
        recording = await asyncio.to_thread(self._decode, request.audio)

        transcript_data = await self._speech.transcribe_audio(recording)
        speech_analysis = self._speech.analyze_speech_patterns(transcript_data)

        # librosa feature extraction is seconds of synchronous CPU work on a long
        # recording; keep it off the loop so other sessions keep receiving frames.
        voice_analysis = await asyncio.to_thread(self._voice.analyze_audio, recording)
        tone_description = self._voice.get_tone_description(voice_analysis)

        overall_score = scoring_service.calculate_overall_score(
            speech_analysis, voice_analysis, request.emotion_summary,
        )

        feedback = await self._generate_feedback(
            request, transcript_data, speech_analysis, tone_description, voice_analysis,
        )

        return SessionAnalysis(
            duration=request.duration,
            transcript=transcript_data.get("text", ""),
            transcript_is_mock=bool(transcript_data.get("is_mock")),
            transcript_error=transcript_data.get("error"),
            speech_analysis=speech_analysis,
            voice_analysis=voice_analysis,
            tone_description=tone_description,
            emotion_summary=request.emotion_summary,
            feedback=feedback,
            overall_score=overall_score,
            audio_truncated=request.audio_truncated,
        )

    @staticmethod
    def _decode(audio: bytes) -> Optional[DecodedRecording]:
        """Decode the upload, or None if it cannot be read.

        A failure here is reported by each analyser as its own degraded result,
        so the report explains what could not be measured instead of the whole
        analysis raising.
        """
        if not audio:
            return None
        try:
            return DecodedRecording.from_upload(audio)
        except AudioDecodeError as exc:
            logger.warning("Recording could not be decoded: %s", exc)
            return None

    async def _generate_feedback(self, request: AnalysisRequest, transcript_data: Dict,
                                 speech_analysis: Dict, tone_description: str,
                                 voice_analysis: Dict) -> str:
        prompt = self._build_prompt(
            request.topic, request.duration, transcript_data, speech_analysis,
            tone_description, voice_analysis, request.emotion_summary,
        )
        # record_history=False: this machine-generated prompt must not become
        # part of the user-visible conversation context.
        return await self._coach.get_coach_response(
            request.session_id, prompt, request.emotion_summary, record_history=False,
        )
