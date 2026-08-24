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


def _concat(spec, tmp_path) -> bytes:
    """Build a WebM/Opus recording from alternating tone/silence spans.

    `spec` is a list of (kind, seconds) where kind is "tone" or "silence".
    """
    files = []
    for index, (kind, seconds) in enumerate(spec):
        part = tmp_path / f"p{index}.wav"
        source = ("sine=frequency=190" if kind == "tone" else "anullsrc=r=44100:cl=mono")
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", source,
             "-t", str(seconds), str(part)], check=True)
        files.append(part)

    listing = tmp_path / "list.txt"
    listing.write_text("".join(f"file {f}\n" for f in files))
    return subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-c:a", "libopus", "-f", "webm", "pipe:1"],
        stdout=subprocess.PIPE, check=True).stdout


class TestSpeechSegments:
    """Pause statistics used to come from three constants shipped with the mock
    transcript, so every session reported the same pauses. These verify they are
    now measured off the waveform."""

    def test_duration_is_measured_from_the_samples(self, tmp_path):
        from app.utils.audio import wav_duration_seconds

        wav = decode_to_wav(_concat([("tone", 1), ("silence", 1), ("tone", 1)], tmp_path))
        assert wav_duration_seconds(wav) == pytest.approx(3.0, abs=0.1)

    def test_finds_the_spans_between_silences(self, tmp_path):
        from app.utils.audio import detect_speech_segments

        # Ground truth: speech 0-1, silence 1-2, speech 2-3.2, silence 3.2-4.5, speech 4.5-5.5
        wav = decode_to_wav(_concat(
            [("tone", 1), ("silence", 1), ("tone", 1.2), ("silence", 1.3), ("tone", 1)],
            tmp_path))
        segments = detect_speech_segments(wav)

        assert len(segments) == 3
        starts = [s["start"] for s in segments]
        assert starts[0] == pytest.approx(0.0, abs=0.1)
        assert starts[1] == pytest.approx(2.0, abs=0.1)
        assert starts[2] == pytest.approx(4.5, abs=0.1)

    def test_gaps_match_the_real_pauses(self, tmp_path):
        from app.utils.audio import detect_speech_segments

        wav = decode_to_wav(_concat(
            [("tone", 1), ("silence", 1), ("tone", 1.2), ("silence", 1.3), ("tone", 1)],
            tmp_path))
        segments = detect_speech_segments(wav)
        gaps = [segments[i + 1]["start"] - segments[i]["end"] for i in range(len(segments) - 1)]

        assert gaps[0] == pytest.approx(1.0, abs=0.12)
        assert gaps[1] == pytest.approx(1.3, abs=0.12)

    def test_continuous_speech_is_one_segment(self, tmp_path):
        from app.utils.audio import detect_speech_segments

        wav = decode_to_wav(_concat([("tone", 2)], tmp_path))
        assert len(detect_speech_segments(wav)) == 1

    def test_pure_silence_yields_no_segments(self, tmp_path):
        from app.utils.audio import detect_speech_segments

        wav = decode_to_wav(_concat([("silence", 2)], tmp_path))
        assert detect_speech_segments(wav) == []
