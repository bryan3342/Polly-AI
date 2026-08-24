import pytest

from app.services.speech_service import SpeechService


@pytest.fixture
def service():
    return SpeechService()


class TestTranscribeAudio:
    def test_returns_mock_transcript_shape(self, service):
        # transcribe_audio is synchronous: it was previously declared `async`
        # with nothing to await, which misrepresented it as doing I/O.
        result = service.transcribe_audio(b"fake-audio-bytes")

        assert set(result) == {"text", "segments", "duration", "language", "is_mock"}
        assert result["text"]
        assert result["duration"] == 15.0
        assert result["language"] == "en"
        for segment in result["segments"]:
            assert segment["end"] > segment["start"]

    def test_placeholder_transcript_is_flagged(self, service):
        """The transcript is fabricated, so it must be labelled as such."""
        assert service.transcribe_audio(b"")["is_mock"] is True


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
        """Metrics derived from placeholder text must stay labelled as such."""
        transcript = service.transcribe_audio(b"")
        assert service.analyze_speech_patterns(transcript)["is_mock"] is True
