"""Tests for decoding browser-recorded audio.

Regression cover for the bug where `librosa.load()` was handed the raw
MediaRecorder upload. libsndfile cannot demux WebM/Opus, so every real
recording raised "Format not recognised" and voice analysis silently reported
itself degraded -- no user ever saw a measured voice metric.
"""

import struct
import subprocess
import wave

import pytest

from app.utils.audio import AudioDecodeError, decode_to_wav, ffmpeg_available

pytestmark = pytest.mark.skipif(
    not ffmpeg_available(), reason="ffmpeg is required to decode recorded audio"
)


def _encode(fmt: str, codec: str, seconds: float = 1.0, freq: int = 220) -> bytes:
    """Encode a test tone the way a browser would hand it to us."""
    # MP4 normally needs a seekable output to write its index; fragmenting lets
    # it be muxed straight to a pipe, which is also how Safari streams it.
    mp4_flags = ["-movflags", "frag_keyframe+empty_moov"] if fmt == "mp4" else []
    proc = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi",
         "-i", f"sine=frequency={freq}:duration={seconds}",
         "-c:a", codec, *mp4_flags, "-f", fmt, "pipe:1"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    return proc.stdout


def test_raw_webm_is_not_readable_by_libsndfile():
    """The precondition for the bug: the upload format librosa cannot read."""
    soundfile = pytest.importorskip("soundfile")
    import io

    with pytest.raises(Exception):
        soundfile.read(io.BytesIO(_encode("webm", "libopus")))


def test_decodes_chrome_webm_opus():
    wav = decode_to_wav(_encode("webm", "libopus"))
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"


def test_decodes_safari_mp4_aac():
    """Safari's MediaRecorder emits MP4/AAC rather than WebM."""
    wav = decode_to_wav(_encode("mp4", "aac"))
    assert wav[:4] == b"RIFF"


def test_decoded_audio_is_mono_at_the_target_rate():
    import io

    wav = decode_to_wav(_encode("webm", "libopus", seconds=2.0), sample_rate=16000)
    with wave.open(io.BytesIO(wav)) as handle:
        assert handle.getnchannels() == 1
        assert handle.getframerate() == 16000


def test_decoded_audio_preserves_the_signal():
    """Guards against 'decodes fine' paths that yield silence."""
    import io

    wav = decode_to_wav(_encode("webm", "libopus", seconds=1.0))
    with wave.open(io.BytesIO(wav)) as handle:
        frames = handle.readframes(handle.getnframes())
    samples = struct.unpack(f"<{len(frames) // 2}h", frames)
    peak = max(abs(s) for s in samples)
    assert peak > 1000, f"decoded audio is effectively silent (peak={peak})"


def test_empty_payload_is_rejected():
    with pytest.raises(AudioDecodeError, match="empty"):
        decode_to_wav(b"")


def test_garbage_payload_is_rejected():
    """A truncated or corrupt upload must fail loudly, not score as silence."""
    with pytest.raises(AudioDecodeError):
        decode_to_wav(b"this is not audio" * 100)
