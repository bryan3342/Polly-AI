"""Domain scoring for a debate session.

Kept separate from the transport layer so the scoring rules can be unit tested
without a WebSocket, and so changing the rubric touches exactly one file.
"""

from typing import Dict, Optional

# Speaking pace, words per minute.
IDEAL_WPM = (120, 160)
ACCEPTABLE_WPM = (100, 180)

# Emotional composure buckets, keyed by dominant emotion.
EMOTION_SCORES = {
    "happy": 85,
    "neutral": 85,
    "surprise": 75,
    "sad": 50,
    "angry": 50,
    "fear": 50,
}
DEFAULT_EMOTION_SCORE = 70

MAX_FILLER_PENALTY = 20

# Gesture engagement, as a share of frames in which a hand was visible.
#
# Speakers who never bring their hands into view read as stiff; speakers whose
# hands are constantly moving read as distracting. The band between is what
# public-speaking guidance consistently asks for, so it scores full marks and
# either side of it tapers.
IDEAL_HANDS_VISIBLE = (0.25, 0.85)
ACCEPTABLE_HANDS_VISIBLE = (0.10, 0.95)


def score_speech(speech_analysis: Dict) -> Optional[float]:
    """Score speaking pace and filler-word usage. None if no speech data."""
    if not speech_analysis:
        return None

    wpm = speech_analysis.get("words_per_minute")
    if wpm is None:
        return None

    if IDEAL_WPM[0] <= wpm <= IDEAL_WPM[1]:
        score = 100
    elif ACCEPTABLE_WPM[0] <= wpm <= ACCEPTABLE_WPM[1]:
        score = 80
    else:
        score = 60

    filler_pct = speech_analysis.get("filler_percentage", 0)
    score -= min(MAX_FILLER_PENALTY, filler_pct * 2)
    return max(0, score)


def score_emotion(emotion_summary: Dict) -> Optional[float]:
    """Score emotional composure. None if no face was ever detected."""
    emotion_data = (emotion_summary or {}).get("emotion_summary") or {}
    dominant = emotion_data.get("dominant")
    if not dominant:
        return None
    return EMOTION_SCORES.get(dominant, DEFAULT_EMOTION_SCORE)


def score_gestures(emotion_summary: Dict) -> Optional[float]:
    """Score gesture engagement. None if hands were never tracked at all.

    The None case is doing real work here. "No hands were visible" and "hand
    tracking was unavailable" produce the same empty timeline, and only the
    second should be excluded from the score -- so this scores nothing unless
    frames were actually examined. A speaker who kept their hands down *was*
    measured, and scores low for it.
    """
    gestures = (emotion_summary or {}).get("gesture_summary") or {}
    if not gestures.get("frames"):
        return None

    ratio = gestures.get("hands_visible_ratio")
    if ratio is None:
        return None

    if IDEAL_HANDS_VISIBLE[0] <= ratio <= IDEAL_HANDS_VISIBLE[1]:
        return 100.0
    if ACCEPTABLE_HANDS_VISIBLE[0] <= ratio <= ACCEPTABLE_HANDS_VISIBLE[1]:
        return 80.0
    return 60.0


def calculate_overall_score(
    speech_analysis: Dict,
    voice_analysis: Dict,
    emotion_summary: Dict,
) -> Optional[float]:
    """Average the available component scores (0-100).

    Components that could not be measured are omitted rather than defaulted, so a
    failed analysis lowers confidence in the result instead of silently inventing
    an average-looking number. Returns None when nothing could be measured.
    """
    components = [
        score_speech(speech_analysis),
        # A degraded voice analysis carries no confidence value worth scoring.
        None if (voice_analysis or {}).get("degraded") else (voice_analysis or {}).get("confidence_score"),
        score_emotion(emotion_summary),
        score_gestures(emotion_summary),
    ]
    measured = [c for c in components if c is not None]

    if not measured:
        return None
    return round(sum(measured) / len(measured), 1)
