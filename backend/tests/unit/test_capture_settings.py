"""The server tells the client how fast to send frames.

The capture rate is a property of whatever machine runs inference, and the
browser cannot know what that is. Measured per frame: an Apple M4 does
full-resolution detection plus emotion classification in ~39 ms, while a tenth
of a shared core takes ~600 ms. Compiling one number into the frontend meant it
was wrong by more than an order of magnitude in one direction or the other, and
changing it needed a rebuild.

So it is served on connect instead, and these pin that contract down: the field
names travel to the client, and a misspelling here is a silent fallback to the
conservative default rather than a visible failure.
"""

import asyncio

from app.api.websocket import ConnectionManager
from app.config import config


class FakeSocket:
    """Records what the server sends, in order."""

    def __init__(self):
        self.sent = []

    async def accept(self):
        pass

    async def send_json(self, message):
        self.sent.append(message)


class FakeTopics:
    def get_random_topic(self):
        return "Should debate club be mandatory?"


class _Unused:
    def __getattr__(self, name):
        raise AssertionError(f"unexpected call to {name}")


def _connect():
    manager = ConnectionManager(
        emotion_analyzer=_Unused(), coach=_Unused(), topics=FakeTopics(),
        analyzer=_Unused(), repository=_Unused(),
    )
    socket = FakeSocket()
    asyncio.run(manager.connect("s1", socket))
    return socket


def _capture_message(socket):
    for message in socket.sent:
        if message.get("type") == "capture_settings":
            return message
    return None


def test_capture_settings_are_sent_on_connect():
    """Without this the client silently keeps its conservative fallback, and a
    fast machine runs at a fraction of the frame rate it could."""
    message = _capture_message(_connect())

    assert message is not None, "the client was never told what rate to use"


def test_the_settings_carry_the_server_s_configured_values():
    message = _capture_message(_connect())

    assert message["frame_interval_ms"] == config.FRAME_INTERVAL_MS
    assert message["idle_frame_interval_ms"] == config.IDLE_FRAME_INTERVAL_MS
    assert message["jpeg_quality"] == config.FRAME_JPEG_QUALITY


def test_the_idle_rate_is_slower_than_the_recording_rate():
    """Idle frames feed only the live readout; recorded ones build the report."""
    message = _capture_message(_connect())

    assert message["idle_frame_interval_ms"] >= message["frame_interval_ms"]


def test_settings_arrive_before_the_session_can_be_used():
    """They must land before the welcome text invites the user to record."""
    socket = _connect()
    types = [m.get("type") for m in socket.sent]

    assert "capture_settings" in types
    assert types.index("capture_settings") < types.index("chat_response"), (
        "the client should know its capture rate before it is told to start"
    )


def test_local_defaults_are_tuned_for_a_real_machine():
    """The regression this guards: hosted-tier values quietly becoming the
    defaults again, so a local run samples emotion once a second."""
    assert config.FRAME_INTERVAL_MS <= 200, (
        "the default capture rate should suit the machine this runs on; "
        "hosted deployments override it (see render.yaml)"
    )
    assert config.DETECT_WIDTH == 0, (
        "detection should search full resolution by default; downscaling is a "
        "concession to fractional-CPU hosts"
    )
