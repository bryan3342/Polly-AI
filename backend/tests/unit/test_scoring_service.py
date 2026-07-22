from app.services import scoring_service


def test_ideal_pace_scores_full_marks():
    assert scoring_service.score_speech({"words_per_minute": 140}) == 100


def test_filler_words_penalized_up_to_cap():
    clean = scoring_service.score_speech({"words_per_minute": 140, "filler_percentage": 0})
    noisy = scoring_service.score_speech({"words_per_minute": 140, "filler_percentage": 5})
    capped = scoring_service.score_speech({"words_per_minute": 140, "filler_percentage": 90})

    assert noisy == clean - 10
    assert capped == clean - scoring_service.MAX_FILLER_PENALTY


def test_speech_score_is_none_without_data():
    assert scoring_service.score_speech({}) is None
    assert scoring_service.score_speech({"filler_percentage": 3}) is None


def test_emotion_score_is_none_when_no_face_detected():
    assert scoring_service.score_emotion({}) is None
    assert scoring_service.score_emotion({"emotion_summary": {}}) is None


def test_unknown_emotion_falls_back_to_baseline():
    score = scoring_service.score_emotion({"emotion_summary": {"dominant": "disgust"}})
    assert score == scoring_service.DEFAULT_EMOTION_SCORE


def test_degraded_voice_analysis_is_excluded_not_defaulted():
    """A failed voice analysis must not contribute an invented mid-range score."""
    speech = {"words_per_minute": 140}
    emotion = {"emotion_summary": {"dominant": "neutral"}}

    degraded = scoring_service.calculate_overall_score(
        speech, {"confidence_score": None, "degraded": True}, emotion
    )
    # Only speech (100) and emotion (85) counted.
    assert degraded == 92.5

    healthy = scoring_service.calculate_overall_score(
        speech, {"confidence_score": 40}, emotion
    )
    assert healthy == 75.0
    assert degraded != healthy


def test_overall_score_is_none_when_nothing_measurable():
    assert scoring_service.calculate_overall_score({}, {"degraded": True}, {}) is None
