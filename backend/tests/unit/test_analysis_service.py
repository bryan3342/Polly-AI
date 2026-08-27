"""The post-recording analysis sequence.

This logic used to live inline in the WebSocket handler, where exercising it
meant standing up a connection. Extracted, it can be driven with plain fakes, which is the point of the extraction, and why this file needs no stubs, no
event-loop scaffolding and no ML stack.
"""

import asyncio
from typing import Dict

import pytest

from app.services.analysis_service import (
    AnalysisRequest,
    SessionAnalysis,
    SessionAnalysisService,
)


class FakeSpeech:
    def __init__(self, transcript: Dict = None, analysis: Dict = None):
        self._transcript = transcript or {"text": "we should abolish it", "is_mock": False}
        self._analysis = analysis if analysis is not None else {"word_count": 4, "words_per_minute": 130}
        self.received = None

    async def transcribe_audio(self, audio: bytes) -> Dict:
        self.received = audio
        return self._transcript

    def analyze_speech_patterns(self, transcript_data: Dict) -> Dict:
        return self._analysis


class FakeVoice:
    def __init__(self, analysis: Dict = None, tone: str = "confident, steady, varied"):
        self._analysis = analysis if analysis is not None else {"confidence_score": 80}
        self._tone = tone
        self.received = None

    def analyze_audio(self, audio: bytes) -> Dict:
        self.received = audio
        return self._analysis

    def get_tone_description(self, analysis: Dict) -> str:
        return self._tone


class FakeCoach:
    def __init__(self, reply: str = "Strong opening."):
        self._reply = reply
        self.calls = []

    async def get_coach_response(self, session_id, prompt, emotion_summary=None, record_history=True):
        self.calls.append({
            "session_id": session_id, "prompt": prompt,
            "emotion_summary": emotion_summary, "record_history": record_history,
        })
        return self._reply


def _service(speech=None, voice=None, coach=None, prompt_builder=None):
    return SessionAnalysisService(
        speech_service=speech or FakeSpeech(),
        voice_service=voice or FakeVoice(),
        coach_service=coach or FakeCoach(),
        prompt_builder=prompt_builder or (lambda *a, **k: "PROMPT"),
    )


def _request(**overrides):
    defaults = dict(
        session_id="s1", audio=b"audio-bytes", duration=42.0,
        topic={"id": 3, "topic": "AI will create more jobs"},
        emotion_summary={"emotion_summary": {"dominant": "neutral"}},
    )
    defaults.update(overrides)
    return AnalysisRequest(**defaults)


def _run(coro):
    return asyncio.run(coro)


class TestAnalyze:
    def test_produces_a_complete_report(self):
        result = _run(_service().analyze(_request()))

        assert isinstance(result, SessionAnalysis)
        assert result.transcript == "we should abolish it"
        assert result.tone_description == "confident, steady, varied"
        assert result.feedback == "Strong opening."
        assert result.duration == 42.0

    def test_the_recording_is_decoded_once_and_shared(self):
        """Both analysers need PCM. Decoding per-analyser meant two ffmpeg
        subprocesses per recording and two places agreeing on decode settings."""
        speech, voice = FakeSpeech(), FakeVoice()
        service = _service(speech=speech, voice=voice)

        decodes = []
        sentinel = object()
        service._decode = lambda audio: (decodes.append(audio), sentinel)[1]

        _run(service.analyze(_request(audio=b"take-one")))

        assert decodes == [b"take-one"], "the upload must be decoded exactly once"
        assert speech.received is sentinel
        assert voice.received is sentinel

    def test_an_undecodable_upload_degrades_instead_of_raising(self):
        """The report must explain what could not be measured."""
        speech = FakeSpeech(transcript={"text": "", "is_mock": True, "error": "no audio"},
                            analysis={})
        voice = FakeVoice(analysis={"degraded": True}, tone="unavailable")
        service = _service(speech=speech, voice=voice)

        result = _run(service.analyze(_request(audio=b"not audio at all")))

        assert speech.received is None and voice.received is None
        assert result.transcript_is_mock is True
        assert result.voice_analysis_degraded is True

    def test_feedback_prompt_does_not_enter_conversation_history(self):
        """A machine-generated prompt must not become user-visible context."""
        coach = FakeCoach()
        _run(_service(coach=coach).analyze(_request()))

        assert coach.calls[0]["record_history"] is False

    def test_score_combines_the_measured_components(self):
        result = _run(_service().analyze(_request()))
        assert result.overall_score is not None

    def test_nothing_measurable_yields_no_score(self):
        """Rather than inventing an average-looking number."""
        service = _service(
            speech=FakeSpeech(transcript={"text": "", "is_mock": True}, analysis={}),
            voice=FakeVoice(analysis={"degraded": True, "confidence_score": None}),
        )
        result = _run(service.analyze(_request(emotion_summary={})))

        assert result.overall_score is None
        assert result.voice_analysis_degraded is True


class TestPayload:
    def test_payload_carries_the_degradation_flags(self):
        service = _service(
            speech=FakeSpeech(transcript={"text": "", "is_mock": True, "error": "no key"}, analysis={}),
            voice=FakeVoice(analysis={"degraded": True}),
        )
        payload = _run(service.analyze(_request(audio_truncated=True))).to_payload()

        assert payload["transcript_is_mock"] is True
        assert payload["transcript_error"] == "no key"
        assert payload["voice_analysis_degraded"] is True
        assert payload["audio_truncated"] is True

    def test_payload_shape_is_stable(self):
        """The client reads these keys; adding is safe, renaming is not."""
        payload = _run(_service().analyze(_request())).to_payload()

        assert set(payload) == {
            "transcript", "transcript_is_mock", "transcript_error",
            "speech_analysis", "voice_analysis", "voice_analysis_degraded",
            "tone_description", "emotion_summary", "feedback", "duration",
            "overall_score", "audio_truncated",
        }


class TestRecord:
    def test_record_carries_the_topic_and_score(self):
        result = _run(_service().analyze(_request()))
        record = result.to_record("s1", {"id": 3, "topic": "AI will create more jobs"})

        assert record["session_id"] == "s1"
        assert record["topic_id"] == 3
        assert record["topic_text"] == "AI will create more jobs"
        assert record["overall_score"] == result.overall_score

    def test_an_unusable_transcript_is_never_stored_as_speech(self):
        """Regression: placeholder text was persisted as the user's own words."""
        service = _service(
            speech=FakeSpeech(transcript={"text": "placeholder", "is_mock": True}, analysis={}),
        )
        record = _run(service.analyze(_request())).to_record("s1", {})

        assert record["transcript"] == ""

    def test_payload_and_record_agree_on_the_shared_values(self):
        """Both derive from one object, so they cannot drift apart."""
        result = _run(_service().analyze(_request()))
        payload, record = result.to_payload(), result.to_record("s1", {})

        assert payload["duration"] == record["duration"]
        assert payload["overall_score"] == record["overall_score"]
        assert payload["feedback"] == record["ai_feedback"]
        assert payload["voice_analysis"] == record["voice_analysis"]
