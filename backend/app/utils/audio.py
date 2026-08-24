"""Decoding of browser-recorded audio into something librosa can read.

The frontend captures with MediaRecorder, which emits WebM/Opus on Chrome and
Firefox and MP4/AAC on Safari. libsndfile -- and therefore librosa's default
loader -- understands neither container, so `librosa.load()` on the raw upload
raises "Format not recognised" for *every* real recording. Voice analysis then
fell through to its degraded path on every session, so no user has ever seen a
measured pitch, energy or confidence number.

ffmpeg reads all of those containers and is already installed in the runtime
image (see Dockerfile), so uploads are transcoded to plain PCM WAV first.
"""

import contextlib
import io
import logging
import shutil
import subprocess
import wave
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# librosa resamples anyway; 16 kHz mono is plenty for speech features and keeps
# the intermediate buffer small.
TARGET_SAMPLE_RATE = 16000
DECODE_TIMEOUT_SECONDS = 30


class AudioDecodeError(RuntimeError):
    """Raised when an upload could not be decoded into PCM audio."""


def ffmpeg_available() -> bool:
    """True if the ffmpeg binary can be found on PATH."""
    return shutil.which("ffmpeg") is not None


def decode_to_wav(raw: bytes, sample_rate: int = TARGET_SAMPLE_RATE) -> bytes:
    """Transcode arbitrary recorded audio to mono PCM WAV bytes.

    Accepts any container ffmpeg can demux (WebM/Opus, MP4/AAC, Ogg, WAV...).
    Raises AudioDecodeError -- never returns partial or silent audio -- so the
    caller can report a real failure instead of scoring fabricated silence.
    """
    if not raw:
        raise AudioDecodeError("empty audio payload")

    if not ffmpeg_available():
        raise AudioDecodeError(
            "ffmpeg is not installed; cannot decode browser audio "
            "(install ffmpeg or use the provided Docker image)"
        )

    command = [
        "ffmpeg",
        "-loglevel", "error",
        "-i", "pipe:0",       # read the upload from stdin
        "-f", "wav",
        "-ac", "1",           # mono
        "-ar", str(sample_rate),
        "pipe:1",             # write WAV to stdout
    ]

    try:
        proc = subprocess.run(
            command,
            input=raw,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=DECODE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise AudioDecodeError(
            f"audio decode timed out after {DECODE_TIMEOUT_SECONDS}s"
        ) from exc
    except OSError as exc:  # ffmpeg vanished between the check and the call
        raise AudioDecodeError(f"could not run ffmpeg: {exc}") from exc

    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()[:300]
        raise AudioDecodeError(f"ffmpeg failed to decode audio: {detail}")

    # A WAV header alone is 44 bytes; anything at or below that carries no samples.
    if len(proc.stdout) <= 44:
        raise AudioDecodeError("decoded audio contained no samples")

    logger.debug("Decoded %d bytes of recorded audio to %d bytes of PCM WAV",
                 len(raw), len(proc.stdout))
    return proc.stdout


def read_wav_mono(wav_bytes: bytes) -> Tuple["np.ndarray", int]:
    """Read PCM WAV bytes into a float32 array in [-1, 1] plus its sample rate.

    Uses the stdlib `wave` module rather than librosa so that speech-pattern
    analysis stays importable (and testable) without the heavy audio stack.
    """
    import numpy as np

    with contextlib.closing(wave.open(io.BytesIO(wav_bytes), "rb")) as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())

    if width != 2:
        raise AudioDecodeError(f"expected 16-bit PCM, got {width * 8}-bit")

    samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples, rate


def wav_duration_seconds(wav_bytes: bytes) -> float:
    """Duration of PCM WAV bytes, measured from the samples themselves."""
    samples, rate = read_wav_mono(wav_bytes)
    return float(len(samples) / rate) if rate else 0.0


def detect_speech_segments(
    wav_bytes: bytes,
    frame_ms: int = 30,
    silence_ratio: float = 0.08,
    min_segment_ms: int = 150,
) -> List[Dict[str, float]]:
    """Find voiced spans in PCM WAV audio as [{"start": s, "end": s}, ...].

    Pause statistics used to be derived from three hardcoded segments shipped
    with the mock transcript, so every session reported identical pauses. These
    are measured off the waveform instead: frame energy is compared against a
    threshold relative to the recording's own loudness, so it adapts to quiet
    and loud speakers alike.
    """
    import numpy as np

    samples, rate = read_wav_mono(wav_bytes)
    if samples.size == 0 or rate <= 0:
        return []

    frame_len = max(1, int(rate * frame_ms / 1000))
    usable = (samples.size // frame_len) * frame_len
    if usable == 0:
        return []

    frames = samples[:usable].reshape(-1, frame_len)
    energy = np.sqrt((frames ** 2).mean(axis=1))

    # Threshold relative to a high percentile rather than the max, so one click
    # or pop does not drag the whole threshold up and swallow real speech.
    reference = float(np.percentile(energy, 95))
    if reference <= 0:
        return []
    voiced = energy >= reference * silence_ratio

    segments: List[Dict[str, float]] = []
    start: Optional[int] = None
    for index, is_voiced in enumerate(voiced):
        if is_voiced and start is None:
            start = index
        elif not is_voiced and start is not None:
            segments.append({"start": start, "end": index})
            start = None
    if start is not None:
        segments.append({"start": start, "end": len(voiced)})

    seconds_per_frame = frame_len / rate
    min_frames = max(1, int(min_segment_ms / frame_ms))
    return [
        {
            "start": round(s["start"] * seconds_per_frame, 3),
            "end": round(s["end"] * seconds_per_frame, 3),
        }
        for s in segments
        if s["end"] - s["start"] >= min_frames
    ]
