from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from agentops.llm import LLMClient, LLMError, LLMRequest, LLMResponse


def test_llm_request_holds_documented_fields_and_defaults() -> None:
    # 裁决调用要尽量可复现：温度默认 0，max_tokens 有稳定默认。
    request = LLMRequest(system="judge role", user="finding context")

    assert request.system == "judge role"
    assert request.user == "finding context"
    assert request.max_tokens == 1024
    assert request.temperature == 0.0


def test_llm_request_is_frozen() -> None:
    request = LLMRequest(system="s", user="u")

    with pytest.raises(FrozenInstanceError):
        request.system = "other"  # type: ignore[misc]


def test_llm_response_holds_text_and_is_frozen() -> None:
    response = LLMResponse(text="hello")

    assert response.text == "hello"
    with pytest.raises(FrozenInstanceError):
        response.text = "changed"  # type: ignore[misc]


def test_llm_error_is_a_runtime_error() -> None:
    # 统一失败类型：调用方只需 except LLMError 即可降级。
    assert issubclass(LLMError, RuntimeError)


def test_llm_client_protocol_is_runtime_checkable() -> None:
    class _Stub:
        def complete(self, request: LLMRequest) -> LLMResponse:
            return LLMResponse(text="ok")

    assert isinstance(_Stub(), LLMClient)


def test_object_without_complete_does_not_satisfy_protocol() -> None:
    class _NotAClient:
        pass

    assert not isinstance(_NotAClient(), LLMClient)
