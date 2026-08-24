"""The event loop must stay responsive while analysis runs.

DeepFace inference and librosa feature extraction are synchronous CPU work. Run
directly inside a coroutine they stalled the *whole server*: with one client
uploading a frame per second, every other connected session stopped receiving
messages for the duration of each inference (issue #23).

These tests drive the real ConnectionManager code path with a deliberately slow
blocking analyzer and assert that unrelated coroutines keep making progress.
"""

import asyncio
import importlib
import sys
import time
import types

import pytest


def _stub(name, **attrs):
    """Register a stand-in module, but never shadow a real installation."""
    if name in sys.modules:
        return sys.modules[name]
    try:
        return importlib.import_module(name)
    except ImportError:
        module = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[name] = module
        return module


# The transport layer imports opencv/deepface/pillow transitively. Stubbing them
# keeps this test runnable in CI, which deliberately does not install the ML stack.
_stub("cv2", data=types.SimpleNamespace(haarcascades=""), CascadeClassifier=lambda *a, **k: None,
      cvtColor=lambda *a, **k: None, COLOR_BGR2GRAY=0, COLOR_BGR2RGB=0, COLOR_RGB2BGR=0,
      imdecode=lambda *a, **k: None, IMREAD_COLOR=1)
_stub("deepface", DeepFace=types.SimpleNamespace(analyze=lambda *a, **k: []))
_stub("librosa", load=lambda *a, **k: (None, None),
      feature=types.SimpleNamespace(), effects=types.SimpleNamespace())

# google-genai reads PIL.Image.Image at import time, so the stub needs that
# attribute chain rather than a bare namespace.
_pil_image = _stub("PIL.Image", Image=type("Image", (), {}), open=lambda *a, **k: None)
_stub("PIL", Image=_pil_image)

websocket = pytest.importorskip("app.api.websocket")

BLOCKING_SECONDS = 0.30
TICK_SECONDS = 0.01


def _manager(blocking_seconds=BLOCKING_SECONDS):
    """A ConnectionManager whose frame analysis blocks for a known duration."""
    manager = websocket.ConnectionManager.__new__(websocket.ConnectionManager)
    manager.active_connections = {}
    manager.session_data = {}
    manager._inference_slots = asyncio.Semaphore(2)

    def slow_analyze(frame_data):
        time.sleep(blocking_seconds)          # synchronous, like DeepFace
        return {"face_detected": False}

    manager._analyze_frame_blocking = slow_analyze
    return manager


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
        f"{BLOCKING_SECONDS}s analysis — it is being blocked"
    )


def test_one_session_analysis_does_not_stall_another_session():
    """The user-visible symptom: everyone else's video freezes.

    Asserts on *when* the other session finished, not merely that it eventually
    did. A blocked loop still completes the other work — just not until the
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
        f"{BLOCKING_SECONDS}s analysis — it was stalled behind it"
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
