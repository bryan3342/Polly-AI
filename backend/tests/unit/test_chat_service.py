"""Tests for the Gemini-backed coaching service.

No network: the SDK client is replaced with a stub, so these assert how we
call Gemini and how we handle its answers, not Gemini itself.
"""

import asyncio
import types as pytypes

from app.services.chat_service import MODEL_NAME, ChatService


class _StubModels:
    def __init__(self, replies=None, error=None):
        self._replies = list(replies or [])
        self._error = error
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self._error is not None:
            raise self._error
        text = self._replies.pop(0) if self._replies else "ok"
        return pytypes.SimpleNamespace(text=text)


def _service(replies=None, error=None):
    svc = ChatService.__new__(ChatService)   # bypass __init__ so no real client is built
    svc.api_key = "test-key"
    svc._chats = {}
    svc.client = pytypes.SimpleNamespace(models=_StubModels(replies, error))
    return svc


def _run(coro):
    return asyncio.run(coro)


def test_returns_the_model_reply_and_records_history():
    svc = _service(["Lead with your strongest claim."])
    reply = _run(svc.get_coach_response("s1", "How do I open?"))

    assert reply == "Lead with your strongest claim."
    assert svc.get_history("s1") == [
        {"role": "user", "content": "How do I open?"},
        {"role": "assistant", "content": "Lead with your strongest claim."},
    ]


def test_uses_the_configured_model():
    svc = _service()
    _run(svc.get_coach_response("s1", "hi"))
    assert svc.client.models.calls[0]["model"] == MODEL_NAME


def test_history_is_sent_as_typed_roles_not_a_flattened_string():
    """Regression: the old SDK path concatenated turns into one labelled blob."""
    svc = _service(["first", "second"])
    _run(svc.get_coach_response("s1", "one"))
    _run(svc.get_coach_response("s1", "two"))

    contents = svc.client.models.calls[1]["contents"]
    assert [c.role for c in contents] == ["user", "model", "user"]
    assert contents[-1].parts[0].text == "two"


def test_analysis_prompts_do_not_pollute_chat_history():
    svc = _service(["report"])
    _run(svc.get_coach_response("s1", "INTERNAL ANALYSIS PROMPT", record_history=False))
    assert svc.get_history("s1") == []


def test_emotion_summary_rides_in_the_system_instruction():
    svc = _service()
    _run(svc.get_coach_response("s1", "hi", {"emotion_summary": {"dominant": "sad"}}))
    assert "sad" in svc.client.models.calls[0]["config"].system_instruction


def test_history_is_capped():
    svc = _service(["r"] * 30)
    for i in range(30):
        _run(svc.get_coach_response("s1", f"msg {i}"))
    sent = svc.client.models.calls[-1]["contents"]
    assert len(sent) <= 21   # 20 history turns + the new prompt


def test_missing_api_key_reports_configuration_error():
    svc = ChatService.__new__(ChatService)
    svc.api_key = None
    svc.client = None
    svc._chats = {}
    assert "not configured" in _run(svc.get_coach_response("s1", "hi"))


def test_empty_model_response_is_not_returned_as_a_reply():
    """An empty completion must not be recorded as the coach's answer."""
    svc = _service([""])
    reply = _run(svc.get_coach_response("s1", "hi"))
    assert reply == "I'm having trouble responding right now. Please try again."
    assert svc.get_history("s1") == []


def test_auth_failure_is_reported_distinctly():
    svc = _service(error=RuntimeError("403 API key not valid"))
    assert "AI configuration" in _run(svc.get_coach_response("s1", "hi"))


def test_clear_history_drops_the_session():
    svc = _service(["a"])
    _run(svc.get_coach_response("s1", "hi"))
    svc.clear_history("s1")
    assert svc.get_history("s1") == []
