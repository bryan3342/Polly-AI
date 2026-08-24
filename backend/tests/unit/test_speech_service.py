"""Tests for transcription and speech-pattern analysis.

No network: the Gemini client is stubbed, so these cover how we call it and how
we handle each kind of answer.
"""

import asyncio
import subprocess
import types as pytypes

import pytest

from app.services.speech_service import SpeechService
from app.utils.audio import DecodedRecording, ffmpeg_available

needs_ffmpeg = pytest.mark.skipif(
    not ffmpeg_available(), reason="ffmpeg is required to decode recorded audio"
)


@pytest.fixture
def service():
    """A service with no API key, i.e. transcription unavailable."""
    svc = SpeechService.__new__(SpeechService)
    svc.api_key = None
    svc.client = None
    return svc


def _with_client(reply=None, error=None):
    """A service whose Gemini client returns `reply` (or raises `error`)."""
    svc = SpeechService.__new__(SpeechService)
    svc.api_key = "test-key"

    calls = []

    def generate_content(*, model, contents):
        calls.append({"model": model, "contents": contents})
        if error is not None:
            raise error
        return pytypes.SimpleNamespace(text=reply)

    svc.client = pytypes.SimpleNamespace(models=pytypes.SimpleNamespace(generate_content=generate_content))
    svc.calls = calls
    return svc


def _spoken_audio(seconds: float = 2.0) -> DecodedRecording:
    """A decoded tone, as the analyser hands it to the service.

    Decoding is the caller's responsibility now, so the service is given a
    DecodedRecording rather than the raw upload.
    """
    upload = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi",
         "-i", f"sine=frequency=180:duration={seconds}",
         "-c:a", "libopus", "-f", "webm", "pipe:1"],
        stdout=subprocess.PIPE, check=True,
    ).stdout
    return DecodedRecording.from_upload(upload)


def _run(coro):
    return asyncio.run(coro)


class TestTranscribeAudio:
    RESULT_KEYS = {"text", "segments", "duration", "language", "is_mock", "error"}

    @needs_ffmpeg
    def test_without_an_api_key_returns_no_words_rather_than_inventing_them(self, service):
        """Regression: this used to return a fabricated paragraph of praise.

        That text was scored, shown in the report and persisted as though the
        user had spoken it.
        """
        result = _run(service.transcribe_audio(_spoken_audio(1.0)))

        assert result["text"] == ""
        assert result["is_mock"] is True
        assert "GEMINI_API_KEY" in result["error"]

    def test_no_recording_is_reported_not_transcribed(self, service):
        """The caller passes None when the upload could not be decoded."""
        result = _run(service.transcribe_audio(None))

        assert result["text"] == ""
        assert result["is_mock"] is True
        assert "no audio" in result["error"]

    @needs_ffmpeg
    def test_returns_the_transcript_and_measures_the_recording(self):
        svc = _with_client(reply="Standardized testing does not measure intelligence.")
        result = _run(svc.transcribe_audio(_spoken_audio(2.0)))

        assert result["text"] == "Standardized testing does not measure intelligence."
        assert result["is_mock"] is False
        # Duration is measured off the waveform, not asserted by the model.
        assert result["duration"] == pytest.approx(2.0, abs=0.15)
        assert set(result) <= TestTranscribeAudio.RESULT_KEYS

    @needs_ffmpeg
    def test_sends_the_audio_to_the_model(self):
        svc = _with_client(reply="hello")
        _run(svc.transcribe_audio(_spoken_audio(1.0)))

        contents = svc.calls[0]["contents"]
        audio_parts = [c for c in contents if getattr(c, "inline_data", None) is not None]
        assert audio_parts, "the recording itself must be sent to the model"
        assert audio_parts[0].inline_data.mime_type == "audio/wav"

    @needs_ffmpeg
    def test_no_speech_marker_yields_no_transcript(self):
        svc = _with_client(reply="(no speech detected)")
        result = _run(svc.transcribe_audio(_spoken_audio(1.0)))

        assert result["text"] == ""
        assert result["is_mock"] is True

    @needs_ffmpeg
    def test_empty_model_reply_yields_no_transcript(self):
        svc = _with_client(reply="")
        assert _run(svc.transcribe_audio(_spoken_audio(1.0)))["is_mock"] is True

    @needs_ffmpeg
    def test_api_failure_degrades_instead_of_raising(self):
        svc = _with_client(error=RuntimeError("503 backend unavailable"))
        result = _run(svc.transcribe_audio(_spoken_audio(1.0)))

        assert result["text"] == ""
        assert result["is_mock"] is True
        assert "503" in result["error"]

    @needs_ffmpeg
    def test_pauses_are_measured_from_the_waveform(self):
        """Pause stats used to come from three hardcoded segments.

        Every session therefore reported identical pauses regardless of how the
        user actually spoke.
        """
        svc = _with_client(reply="one two three")
        result = _run(svc.transcribe_audio(_spoken_audio(2.0)))

        assert result["segments"], "expected measured speech spans"
        assert all(s["end"] > s["start"] for s in result["segments"])
        assert max(s["end"] for s in result["segments"]) <= result["duration"] + 0.1


class TestAnalyzeSpeechPatterns:
    def test_empty_text_returns_empty_dict(self, service):
        assert service.analyze_speech_patterns({"text": "", "segments": [], "duration": 10}) == {}

    def test_zero_duration_returns_empty_dict(self, service):
        assert service.analyze_speech_patterns({"text": "hello world", "segments": [], "duration": 0}) == {}

    def test_word_count_and_pace(self, service):
        text = " ".join(["word"] * 30)
        result = service.analyze_speech_patterns({"text": text, "segments": [], "duration": 60})

        assert result["word_count"] == 30
        assert result["words_per_minute"] == 30.0
        assert result["total_speaking_time"] == 60

    def test_pace_scales_with_duration(self, service):
        text = " ".join(["word"] * 30)
        result = service.analyze_speech_patterns({"text": text, "segments": [], "duration": 30})

        assert result["words_per_minute"] == 60.0

    def test_filler_words_counted(self, service):
        text = "I um think that we should uh reconsider the whole plan"
        result = service.analyze_speech_patterns({"text": text, "segments": [], "duration": 10})

        assert result["filler_word_count"] == 2
        assert result["filler_percentage"] == round(2 / 11 * 100, 1)

    def test_no_filler_words(self, service):
        text = "we must reconsider the entire proposal today"
        result = service.analyze_speech_patterns({"text": text, "segments": [], "duration": 10})

        assert result["filler_word_count"] == 0
        assert result["filler_percentage"] == 0

    def test_fillers_at_string_boundaries_and_back_to_back(self, service):
        """Counting is tokenized rather than a scan for ' um ' with surrounding spaces.

        A substring scan misses a filler that starts or ends the transcript, and
        counts adjacent fillers once because they share the separating space.
        """
        result = service.analyze_speech_patterns(
            {"text": "um the point um um stands uh", "segments": [], "duration": 60}
        )

        assert result["filler_word_count"] == 4

    def test_fillers_matched_despite_punctuation(self, service):
        result = service.analyze_speech_patterns(
            {"text": "Um, I think, actually, we agree.", "segments": [], "duration": 60}
        )

        assert result["filler_word_count"] == 2

    def test_pause_detection_ignores_short_gaps(self, service):
        segments = [
            {"start": 0, "end": 5},
            {"start": 5.2, "end": 8},   # 0.2s gap — below the 0.5s threshold
            {"start": 9, "end": 12},    # 1.0s gap — counted
            {"start": 14, "end": 16},   # 2.0s gap — counted
        ]
        result = service.analyze_speech_patterns(
            {"text": "some words here", "segments": segments, "duration": 16}
        )

        assert result["pause_count"] == 2
        assert result["average_pause_duration"] == 1.5

    def test_no_segments_means_no_pauses(self, service):
        result = service.analyze_speech_patterns({"text": "some words", "segments": [], "duration": 5})

        assert result["pause_count"] == 0
        assert result["average_pause_duration"] == 0

    def test_mock_flag_propagates_into_the_analysis(self, service):
        """Metrics derived from unusable text must stay labelled as such."""
        transcript = _run(service.transcribe_audio(None))
        assert transcript["is_mock"] is True
        # No text means no metrics at all, which is the honest result.
        assert service.analyze_speech_patterns(transcript) == {}
