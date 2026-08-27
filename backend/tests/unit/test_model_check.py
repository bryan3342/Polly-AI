"""A retired model must be loud at startup, not quiet during a session.

Google retires model versions. When one goes, the API answers 404 and every
layer above turns it into something reassuring: transcription reports itself
"unavailable", the coach says "I'm having trouble responding right now". Both
read as a missing key or a network blip.

This app shipped with two retired models and was indistinguishable from one with
no API key configured at all. These pin down the check that would have said so.
"""

import logging

import pytest

from app.services import model_check
from app.services.model_check import check_configured_models


@pytest.fixture
def reachable(monkeypatch):
    """Control what the API reports without touching the network."""
    def _set(names, error=None):
        def fake(api_key):
            if error:
                raise error
            return list(names)
        monkeypatch.setattr(model_check, "available_models", fake)
    return _set


def test_configured_models_that_exist_report_no_problem(reachable):
    reachable(["gemini-3.5-flash-lite", "gemini-3.5-flash"])

    assert check_configured_models("k", ["gemini-3.5-flash-lite"]) == []


def test_a_retired_model_is_reported(reachable):
    """The regression: gemini-2.0-flash-lite was retired and nothing said so."""
    reachable(["gemini-3.5-flash-lite"])

    missing = check_configured_models("k", ["gemini-2.0-flash-lite"])

    assert missing == ["gemini-2.0-flash-lite"]


def test_the_report_names_every_missing_model(reachable):
    reachable(["gemini-3.5-flash-lite"])

    missing = check_configured_models(
        "k", ["gemini-2.0-flash", "gemini-3.5-flash-lite", "gemini-2.0-flash-lite"]
    )

    assert missing == ["gemini-2.0-flash", "gemini-2.0-flash-lite"]


def test_a_missing_model_is_logged_at_error_level(reachable, caplog):
    """It has to out-shout the INFO chatter of a normal startup."""
    reachable(["gemini-3.5-flash-lite"])

    with caplog.at_level(logging.ERROR):
        check_configured_models("k", ["gemini-2.0-flash"])

    assert any(r.levelno >= logging.ERROR for r in caplog.records)
    assert "gemini-2.0-flash" in caplog.text


def test_running_without_an_api_key_is_not_a_failure(reachable):
    """A supported mode: the camera, face detection, emotion tracking and voice
    measurement all work without one, and the services say so individually."""
    reachable([])

    assert check_configured_models("", ["gemini-3.5-flash-lite"]) == []


def test_an_unreachable_api_is_not_reported_as_a_retired_model(reachable):
    """'Cannot tell' must not be dressed up as 'the model is gone'. Failing a
    startup over a flaky metadata call would be worse than the fault it
    guards against."""
    reachable([], error=OSError("network down"))

    assert check_configured_models("k", ["gemini-3.5-flash-lite"]) == []


def test_duplicate_names_are_reported_once(reachable):
    """Transcription and coaching commonly point at the same model."""
    reachable([])

    missing = check_configured_models("k", ["gemini-2.0-flash", "gemini-2.0-flash"])

    assert missing == ["gemini-2.0-flash"]
