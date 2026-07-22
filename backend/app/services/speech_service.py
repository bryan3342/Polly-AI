import logging
from typing import Dict

logger = logging.getLogger(__name__)

FILLER_WORDS = ["um", "uh", "like", "you know", "so", "basically", "actually"]
MIN_PAUSE_SECONDS = 0.5

_MOCK_TRANSCRIPT = (
    "Mock transcription: You presented a strong argument about the debate topic. "
    "Your main points were clear and well-structured. You maintained good pacing "
    "throughout your speech."
)


class SpeechService:
    """Speech transcription and pattern analysis.

    Transcription is not yet implemented; `transcribe_audio` returns placeholder
    text flagged with `is_mock=True`. Callers must propagate that flag so the
    fabricated transcript is never presented or stored as a real measurement.
    """

    def __init__(self):
        logger.warning("SpeechService initialized with MOCK transcription (no real STT configured).")

    def transcribe_audio(self, audio_data: bytes) -> Dict:
        """Return a placeholder transcript.

        Replace with a real STT call (Google Cloud Speech / Gemini Audio) and drop
        the `is_mock` flag when doing so.
        """
        return {
            "text": _MOCK_TRANSCRIPT,
            "segments": [
                {"start": 0, "end": 5},
                {"start": 5, "end": 10},
                {"start": 10, "end": 15},
            ],
            "duration": 15.0,
            "language": "en",
            "is_mock": True,
        }

    def analyze_speech_patterns(self, transcript_data: Dict) -> Dict:
        """Analyze speech patterns from a transcript."""
        text = transcript_data.get("text", "")
        segments = transcript_data.get("segments", [])
        duration = transcript_data.get("duration", 0)

        if not text or not duration:
            return {}

        words = text.split()
        word_count = len(words)
        wpm = (word_count / duration) * 60

        # Count on the tokenized words so fillers at the start/end of the text and
        # back-to-back fillers ("um um") are both counted, which a substring scan
        # for " um " misses.
        normalized = [w.strip(".,!?;:").lower() for w in words]
        single_fillers = {f for f in FILLER_WORDS if " " not in f}
        filler_count = sum(1 for w in normalized if w in single_fillers)

        text_lower = " ".join(normalized)
        for phrase in (f for f in FILLER_WORDS if " " in f):
            filler_count += text_lower.count(phrase)

        pauses = []
        for i in range(len(segments) - 1):
            gap = segments[i + 1].get("start", 0) - segments[i].get("end", 0)
            if gap > MIN_PAUSE_SECONDS:
                pauses.append(gap)

        avg_pause = sum(pauses) / len(pauses) if pauses else 0

        return {
            "word_count": word_count,
            "words_per_minute": round(wpm, 1),
            "filler_word_count": filler_count,
            "filler_percentage": round((filler_count / word_count * 100), 1) if word_count else 0,
            "pause_count": len(pauses),
            "average_pause_duration": round(avg_pause, 2),
            "total_speaking_time": round(duration, 1),
            # Propagated so downstream consumers know these metrics describe
            # placeholder text rather than the user's actual speech.
            "is_mock": bool(transcript_data.get("is_mock")),
        }
