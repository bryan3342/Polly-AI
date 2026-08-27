"""Idle connections are closed so the host can scale to zero.

This is a cost control, not hygiene. On a per-request-billed host an open
WebSocket counts as an in-flight request for its entire life, so a browser tab
left open in the background bills CPU and memory around the clock while doing
nothing. Cloud Run's free tier is 180,000 vCPU-seconds a month -- about 50 hours
of *connected* time -- so abandoned tabs are the difference between the app
being free and not.

The transport layer is imported directly, with no `sys.modules` surgery: these
run in CI, where none of the ML stack is installed.
"""

import asyncio

from app.api.websocket import WS_CLOSE_IDLE, receive_or_idle


class FakeSocket:
    """A socket whose next message arrives after `delay` seconds, or never."""

    def __init__(self, message="{}", delay=0.0, never=False):
        self._message = message
        self._delay = delay
        self._never = never
        self.receive_calls = 0

    async def receive_text(self):
        self.receive_calls += 1
        if self._never:
            await asyncio.Event().wait()      # blocks until cancelled
        await asyncio.sleep(self._delay)
        return self._message


def test_a_talkative_connection_is_never_reaped():
    socket = FakeSocket(message='{"type":"frame"}', delay=0.01)

    result = asyncio.run(receive_or_idle(socket, "s1", timeout=0.5))

    assert result == '{"type":"frame"}'


def test_a_silent_connection_reports_idle():
    """The regression this protects: a hidden tab holding an instance alive.

    Browsers keep running a hidden tab's timers, just throttled -- so the client
    also has to stop sending while hidden for this to ever fire. Both halves are
    required; see the document.hidden guard in VideoBox.jsx.
    """
    socket = FakeSocket(never=True)

    result = asyncio.run(receive_or_idle(socket, "s1", timeout=0.05))

    assert result is None, "a silent connection should be reported as idle"


def test_idle_is_reported_rather_than_raised():
    """`None` keeps 'the user left' distinct from 'the connection broke'; they
    need different close codes and different client behaviour."""
    socket = FakeSocket(never=True)

    # Notably does not raise asyncio.TimeoutError at the caller.
    assert asyncio.run(receive_or_idle(socket, "s1", timeout=0.05)) is None


def test_timeout_of_zero_disables_reaping():
    """Always-on hosts have no per-request billing to save, and reaping there
    only costs the user their topic and coaching history."""
    socket = FakeSocket(message='{"type":"chat"}', delay=0.05)

    result = asyncio.run(receive_or_idle(socket, "s1", timeout=0))

    assert result == '{"type":"chat"}'
    assert socket.receive_calls == 1


def test_the_idle_close_code_is_in_the_application_range():
    """4000-4999 is reserved for application use, so it cannot be confused with
    a protocol-level close the client should treat as an error."""
    assert 4000 <= WS_CLOSE_IDLE <= 4999
