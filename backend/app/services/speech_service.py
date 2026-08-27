"""Speech transcription and speech-pattern analysis.

Transcription runs the recorded audio through Gemini's audio understanding.
When no API key is configured the service degrades explicitly (`is_mock=True`,
empty text) rather than returning the fabricated paragraph it used to ship,
which flowed into the score and the report as though the user had said it.
"""

import asyncio
import logging
from typing import Dict, List, Optional

from google import genai
from google.genai import types

from app.config import config
from app.utils.audio import DecodedRecording

logger = logging.getLogger(__name__)

FILLER_WORDS = ["um", "uh", "like", "you know", "so", "basically", "actually"]
MIN_PAUSE_SECONDS = 0.5

# Configurable, and versioned: model names expire.
# See Config.TRANSCRIPTION_MODEL for the measurements behind this choice.
TRANSCRIPTION_MODEL = config.TRANSCRIPTION_MODEL

TRANSCRIPTION_PROMPT = (
    "Transcribe this recording of a person practising a debate argument.\n"
    "Rules:\n"
    "- Output only the words spoken, as a single plain-text paragraph.\n"
    "- Transcribe verbatim. Keep filler words exactly as spoken "
    "(um, uh, like, you know, so, basically, actually). Do not clean them up.\n"
    "- Do not add commentary, headings, speaker labels, or timestamps.\n"
    "- If the audio contains no intelligible speech, output exactly: (no speech detected)"
)

NO_SPEECH_MARKER = "(no speech detected)"

# Gemini bills and rate-limits by input size; ~10 minutes of 16 kHz mono PCM.
MAX_TRANSCRIBE_BYTES = 20 * 1024 * 1024


class SpeechService:
    """Transcribes recorded audio and derives speaking-pattern metrics."""

    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        if not self.client:
            logger.warning(
                "GEMINI_API_KEY is not set; transcription is unavailable and "
                "sessions will report no transcript."
            )
        else:
            logger.info("SpeechService initialized (model=%s).", TRANSCRIPTION_MODEL)

    async def transcribe_audio(self, recording: DecodedRecording) -> Dict:
        """Transcribe a decoded recording.

        Returns the transcript plus `duration` and `segments` measured from the
        waveform, so pause statistics describe the actual recording rather than
        placeholder values. Decoding is the caller's job so one recording is
        decoded once, not once per analyser.
        """
        if not recording:
            return self._unavailable("no audio to transcribe")

        wav_bytes = recording.wav_bytes
        duration = recording.duration_seconds
        segments = recording.speech_segments

        if not self.client:
            return self._unavailable(
                "transcription unavailable (GEMINI_API_KEY is not configured)",
                duration=duration,
                segments=segments,
            )

        if len(wav_bytes) > MAX_TRANSCRIBE_BYTES:
            return self._unavailable(
                "recording is too long to transcribe",
                duration=duration,
                segments=segments,
            )

        try:
            # Blocking network call: keep it off the event loop or every other
            # connected session stalls for its duration.
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=TRANSCRIPTION_MODEL,
                contents=[
                    TRANSCRIPTION_PROMPT,
                    types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav"),
                ],
            )
            text = (response.text or "").strip()
        except Exception as exc:
            logger.exception("Transcription request failed")
            return self._unavailable(
                f"transcription failed: {exc}", duration=duration, segments=segments
            )

        if not text or text.lower().startswith(NO_SPEECH_MARKER[:18]):
            return self._unavailable(
                "no intelligible speech detected", duration=duration, segments=segments
            )

        return {
            "text": text,
            "segments": segments,
            "duration": round(duration, 2),
            "language": "en",
            "is_mock": False,
        }

    @staticmethod
    def _unavailable(
        reason: str,
        duration: float = 0.0,
        segments: Optional[List[Dict]] = None,
    ) -> Dict:
        """A transcript result that carries no words.

        `is_mock` stays True so callers keep treating the text as unusable; the
        difference from the old behaviour is that the text really is empty
        instead of being an invented paragraph of praise.
        """
        return {
            "text": "",
            "segments": segments or [],
            "duration": round(duration, 2),
            "language": "en",
            "is_mock": True,
            "error": reason,
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
