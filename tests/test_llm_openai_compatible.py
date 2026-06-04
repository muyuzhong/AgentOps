from __future__ import annotations

import email.message
import io
import json
import urllib.error
import urllib.request

import pytest

from agentops.llm import LLMError, LLMRequest, LLMResponse
from agentops.llm.openai_compatible import OpenAICompatibleClient


class _FakeHTTPResponse:
    """最小的 urlopen 返回值替身：支持上下文管理器和 read()。"""

    def __init__(self, payload: object) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def _capture_urlopen(
    captured: dict[str, object], payload: object
) -> "callable":
    """返回一个记录请求并回放固定响应的 urlopen 替身。"""

    def fake_urlopen(request: urllib.request.Request, timeout: float | None = None):
        captured["request"] = request
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeHTTPResponse(payload)

    return fake_urlopen


def _ok_payload(content: str) -> dict[str, object]:
    """构造一个 OpenAI 兼容的成功响应。"""

    return {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"total_tokens": 1},
        "model": "mimo-v2.5-pro",
    }


def test_complete_maps_request_to_chat_completions_and_returns_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        urllib.request, "urlopen", _capture_urlopen(captured, _ok_payload("verdict"))
    )
    client = OpenAICompatibleClient(
        model="mimo-v2.5-pro",
        base_url="https://example.test/v1",
        api_key="tp-secret",
    )

    response = client.complete(
        LLMRequest(system="judge role", user="finding context", max_tokens=256)
    )

    assert isinstance(response, LLMResponse)
    assert response.text == "verdict"
    request = captured["request"]
    assert request.full_url == "https://example.test/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer tp-secret"
    body = captured["body"]
    assert body["model"] == "mimo-v2.5-pro"
    assert body["temperature"] == 0.0
    assert body["max_tokens"] == 256
    assert body["messages"] == [
        {"role": "system", "content": "judge role"},
        {"role": "user", "content": "finding context"},
    ]


def test_complete_strips_trailing_slash_from_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        urllib.request, "urlopen", _capture_urlopen(captured, _ok_payload("ok"))
    )
    client = OpenAICompatibleClient(
        model="m", base_url="https://example.test/v1/", api_key="k"
    )

    client.complete(LLMRequest(system="s", user="u"))

    assert captured["request"].full_url == "https://example.test/v1/chat/completions"


def test_complete_without_api_key_raises_llm_error() -> None:
    client = OpenAICompatibleClient(model="m", base_url="https://example.test/v1")

    with pytest.raises(LLMError):
        client.complete(LLMRequest(system="s", user="u"))


def test_complete_wraps_http_error_as_llm_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_http(request: object, timeout: float | None = None):
        raise urllib.error.HTTPError(
            "https://example.test/v1/chat/completions",
            401,
            "Unauthorized",
            email.message.Message(),
            io.BytesIO(b'{"error": "invalid key"}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", raise_http)
    client = OpenAICompatibleClient(model="m", base_url="https://example.test/v1", api_key="k")

    with pytest.raises(LLMError):
        client.complete(LLMRequest(system="s", user="u"))


def test_complete_wraps_network_error_as_llm_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_url(request: object, timeout: float | None = None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", raise_url)
    client = OpenAICompatibleClient(model="m", base_url="https://example.test/v1", api_key="k")

    with pytest.raises(LLMError):
        client.complete(LLMRequest(system="s", user="u"))


def test_complete_wraps_unparsable_response_as_llm_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _BadResponse(_FakeHTTPResponse):
        def read(self) -> bytes:
            return b"not json at all"

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout=None: _BadResponse(None),
    )
    client = OpenAICompatibleClient(model="m", base_url="https://example.test/v1", api_key="k")

    with pytest.raises(LLMError):
        client.complete(LLMRequest(system="s", user="u"))


def test_complete_wraps_missing_content_as_llm_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout=None: _FakeHTTPResponse({"choices": []}),
    )
    client = OpenAICompatibleClient(model="m", base_url="https://example.test/v1", api_key="k")

    with pytest.raises(LLMError):
        client.complete(LLMRequest(system="s", user="u"))


def test_complete_rejects_non_text_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # content 为 null（如纯 tool_calls 响应）应作为 LLMError，便于安全降级。
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout=None: _FakeHTTPResponse(_ok_payload_none()),
    )
    client = OpenAICompatibleClient(model="m", base_url="https://example.test/v1", api_key="k")

    with pytest.raises(LLMError):
        client.complete(LLMRequest(system="s", user="u"))


def _ok_payload_none() -> dict[str, object]:
    return {"choices": [{"message": {"role": "assistant", "content": None}}]}


def test_empty_model_raises_llm_error() -> None:
    # 不在库代码里硬编码默认模型；构造时必须显式给出 model。
    with pytest.raises(LLMError):
        OpenAICompatibleClient(model="", base_url="https://example.test/v1", api_key="k")


def test_construction_makes_no_network_call() -> None:
    # 仅标准库实现：导入与构造都不触网，只有 complete() 才发请求。
    import agentops.llm.openai_compatible as adapter_module

    assert adapter_module is not None
    OpenAICompatibleClient(model="m", base_url="https://example.test/v1", api_key="k")
