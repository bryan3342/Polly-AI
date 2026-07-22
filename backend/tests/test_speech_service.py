from app.services.speech_service import SpeechService


def _service():
    return SpeechService()


def test_empty_transcript_returns_empty_analysis():
    assert _service().analyze_speech_patterns({"text": "", "duration": 10}) == {}
    assert _service().analyze_speech_patterns({"text": "hello", "duration": 0}) == {}


def test_words_per_minute():
    result = _service().analyze_speech_patterns(
        {"text": " ".join(["word"] * 30), "duration": 60, "segments": []}
    )
    assert result["words_per_minute"] == 30.0
    assert result["word_count"] == 30


def test_fillers_counted_at_boundaries_and_back_to_back():
    """The old substring scan for ' um ' missed both of these cases."""
    result = _service().analyze_speech_patterns(
        {"text": "um the point um um stands uh", "duration": 60, "segments": []}
    )
    # leading "um", two adjacent "um"s, and trailing "uh" -> 4
    assert result["filler_word_count"] == 4


def test_fillers_matched_despite_punctuation():
    result = _service().analyze_speech_patterns(
        {"text": "Um, I think, actually, we agree.", "duration": 60, "segments": []}
    )
    assert result["filler_word_count"] == 2


def test_pauses_only_counted_above_threshold():
    segments = [
        {"start": 0, "end": 5},
        {"start": 5.2, "end": 8},    # 0.2s gap -> not a pause
        {"start": 10, "end": 12},    # 2.0s gap -> a pause
    ]
    result = _service().analyze_speech_patterns(
        {"text": "a b c", "duration": 12, "segments": segments}
    )
    assert result["pause_count"] == 1
    assert result["average_pause_duration"] == 2.0


def test_mock_flag_propagates_from_transcript_to_analysis():
    """Placeholder metrics must stay labelled so they are never treated as real."""
    service = _service()
    transcript = service.transcribe_audio(b"")
    assert transcript["is_mock"] is True
    assert service.analyze_speech_patterns(transcript)["is_mock"] is True
