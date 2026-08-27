"""The event loop must stay responsive while analysis runs.

DeepFace inference and librosa feature extraction are synchronous CPU work. Run
directly inside a coroutine they stalled the *whole server*: with one client
uploading a frame per second, every other connected session stopped receiving
messages for the duration of each inference (issue #23).

These tests drive the real ConnectionManager code path with a deliberately slow
blocking analyzer and assert that unrelated coroutines keep making progress.

Note what this file does *not* do: it imports the transport layer directly, with
no `sys.modules` surgery. That is only possible because ConnectionManager now
depends on the protocols in `app.services.protocols` rather than on the
concrete, TensorFlow-backed services.
"""

import asyncio
import time

from app.api.websocket import ConnectionManager


BLOCKING_SECONDS = 0.30
TICK_SECONDS = 0.01


class SlowEmotionAnalyzer:
    """Stands in for DeepFace: synchronous and slow, as the real one is."""

    def __init__(self, blocking_seconds):
        self._blocking_seconds = blocking_seconds

    def analyze_encoded_frame(self, frame_data):
        time.sleep(self._blocking_seconds)
        return {"face_detected": False}

    def calculate_summary(self, emotion_timeline):
        return {}


class _Unused:
    """Collaborators these tests never exercise."""

    def __getattr__(self, name):
        raise AssertionError(f"unexpected call to {name}")


def _manager(blocking_seconds=BLOCKING_SECONDS):
    """A ConnectionManager whose frame analysis blocks for a known duration."""
    return ConnectionManager(
        emotion_analyzer=SlowEmotionAnalyzer(blocking_seconds),
        coach=_Unused(),
        topics=_Unused(),
        analyzer=_Unused(),
        repository=_Unused(),
        max_concurrent_inferences=2,
    )


async def _count_ticks(stop_event):
    """Count how many times the loop gets control while work is in flight."""
    ticks = 0
    while not stop_event.is_set():
        await asyncio.sleep(TICK_SECONDS)
        ticks += 1
    return ticks


def test_frame_analysis_does_not_block_the_event_loop():
    async def scenario():
        manager = _manager()
        stop = asyncio.Event()
        ticker = asyncio.create_task(_count_ticks(stop))

        await manager.process_frame("s1", "frame-data", 0.0)

        stop.set()
        return await ticker

    ticks = asyncio.run(scenario())

    # Blocking the loop would let through ~0 ticks. Offloaded, the loop should
    # tick roughly BLOCKING_SECONDS / TICK_SECONDS times.
    expected = BLOCKING_SECONDS / TICK_SECONDS
    assert ticks > expected * 0.4, (
        f"event loop only ticked {ticks} times during a "
        f"{BLOCKING_SECONDS}s analysis: it is being blocked"
    )


def test_one_session_analysis_does_not_stall_another_session():
    """The user-visible symptom: everyone else's video freezes.

    Asserts on *when* the other session finished, not merely that it eventually
    did. A blocked loop still completes the other work, just not until the
    inference is over, which is exactly the freeze being fixed.
    """
    async def scenario():
        manager = _manager()
        started = time.monotonic()
        finished_at = {}

        async def other_session():
            # 10 x 10ms of ordinary work: far shorter than the 300ms analysis.
            for _ in range(10):
                await asyncio.sleep(TICK_SECONDS)
            finished_at["at"] = time.monotonic() - started

        await asyncio.gather(
            manager.process_frame("busy", "frame-data", 0.0),
            other_session(),
        )
        return finished_at["at"]

    elapsed = asyncio.run(scenario())

    # Concurrent: finishes in ~0.1s. Blocked: not until the 0.3s analysis ends.
    assert elapsed < BLOCKING_SECONDS, (
        f"the second session did not finish until {elapsed:.2f}s, after the "
        f"{BLOCKING_SECONDS}s analysis: it was stalled behind it"
    )


def test_concurrent_inferences_are_bounded():
    """Unbounded threads would thrash CPU/memory on a shared-CPU instance."""
    async def scenario():
        manager = _manager(blocking_seconds=0.15)
        live = 0
        peak = 0
        lock = asyncio.Lock()

        original = manager._analyze_frame_blocking

        def counting_analyze(frame_data):
            nonlocal live, peak
            live += 1
            peak = max(peak, live)
            try:
                return original(frame_data)
            finally:
                live -= 1

        manager._analyze_frame_blocking = counting_analyze
        await asyncio.gather(*(manager.process_frame(f"s{i}", "d", 0.0) for i in range(8)))
        return peak

    peak = asyncio.run(scenario())

    # Exactly the configured limit: >2 means the bound leaks, 1 means the calls
    # are not actually running off the loop in parallel.
    assert peak == 2, f"peak concurrent inferences was {peak}; expected 2"



def _saturating_manager(blocking_seconds=BLOCKING_SECONDS, limit=1):
    """A manager with a single inference slot, as a fractional-CPU host wants."""
    return ConnectionManager(
        emotion_analyzer=SlowEmotionAnalyzer(blocking_seconds),
        coach=_Unused(),
        topics=_Unused(),
        analyzer=_Unused(),
        repository=_Unused(),
        max_concurrent_inferences=limit,
    )


def _seed_session(manager, session_id="s1"):
    """The parts of a live session these tests read.

    Built directly rather than through `connect`, which would assign a topic and
    send a welcome message through collaborators these tests deliberately do not
    provide.
    """
    manager.session_data[session_id] = {
        "frame_count": 0,
        "frames_dropped": 0,
        "emotions": [],
    }
    return manager.session_data[session_id]


class TestFrameBackpressure:
    """Frames are dropped when inference is saturated, never queued.

    Frames arrive on a fixed clock -- once a second while recording -- but
    inference takes however long the host's CPU takes. On a fractional-CPU host
    the second is reliably shorter than the inference, so awaiting a slot built
    an unbounded backlog: latency and memory grew for the whole session, and
    every frame that eventually ran described a moment long past.

    Emotion tracking samples a continuous signal, so a sparser sample is a real
    answer where a minutes-stale one is not.
    """

    def test_frames_arriving_faster_than_inference_are_dropped(self):
        async def scenario():
            manager = _saturating_manager()
            session = _seed_session(manager)
            await asyncio.gather(*(
                manager.process_frame("s1", f"frame-{i}", i * 0.01)
                for i in range(10)
            ))
            return session["frame_count"], session["frames_dropped"]

        analysed, dropped = asyncio.run(scenario())

        assert dropped > 0, "a saturated server must shed frames, not queue them"
        assert analysed + dropped == 10, "every frame is analysed or counted as dropped"

    def test_a_burst_costs_about_one_inference_not_ten(self):
        """The regression: wall time used to grow with the size of the backlog."""
        async def scenario():
            manager = _saturating_manager()
            _seed_session(manager)
            started = time.monotonic()
            await asyncio.gather(*(
                manager.process_frame("s1", f"frame-{i}", i * 0.01) for i in range(10)
            ))
            return time.monotonic() - started

        elapsed = asyncio.run(scenario())

        # Queued, ten frames would take ~10 x BLOCKING_SECONDS.
        assert elapsed < BLOCKING_SECONDS * 2, (
            f"10 frames took {elapsed:.2f}s against a {BLOCKING_SECONDS}s "
            f"inference -- they are being queued, not dropped"
        )

    def test_dropping_is_momentary_not_latched(self):
        """Frames must be analysed again as soon as the server has capacity."""
        async def scenario():
            manager = _saturating_manager(blocking_seconds=0.01)
            session = _seed_session(manager)
            for i in range(3):          # serially: never saturated
                await manager.process_frame("s1", f"frame-{i}", i)
            return session

        session = asyncio.run(scenario())

        assert session["frame_count"] == 3
        assert session["frames_dropped"] == 0
