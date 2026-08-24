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

import logging
import shutil
import subprocess

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
