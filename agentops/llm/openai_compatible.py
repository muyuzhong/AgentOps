"""LLMClient 的 OpenAI 兼容适配器（仅依赖标准库）。

适用于任何讲 OpenAI ``/chat/completions`` 协议的网关（mimo、vLLM、OpenAI 本身）。
刻意只用标准库 ``urllib``：不引入任何运行时/可选依赖，``import agentops`` 永远
不需要第三方 SDK。一切失败——缺 key、网络/HTTP 错误、响应不可解析——都统一抛
``LLMError``，让上层 judge 能安全降级到确定性裁决。

结构化输出（严格 JSON）不在这里处理：本适配器只负责把 system/user 文本送出去，
把模型回复的纯文本带回来；解析与校验是 judge 的职责（见 ``llm_intent``）。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from agentops.llm.client import LLMError, LLMRequest, LLMResponse

# HTTP 错误体只截取一小段进 LLMError 文案，避免把整页报错灌进 stderr。
_MAX_ERROR_DETAIL = 200


class OpenAICompatibleClient:
    """把 ``LLMRequest`` 映射为 OpenAI 兼容的 ``/chat/completions`` 调用。"""

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        # 不在库代码里硬编码模型层级（haiku/sonnet/...）：model 必须由调用方给出。
        if not model:
            raise LLMError("model is required for the OpenAI-compatible client")
        if not base_url:
            raise LLMError("base_url is required for the OpenAI-compatible client")
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    def complete(self, request: LLMRequest) -> LLMResponse:
        """发起一次裁决调用；任何失败都抛 LLMError。"""

        # 缺 key 不发请求，直接交给上层降级。
        if not self._api_key:
            raise LLMError("missing API key for the OpenAI-compatible client")

        payload = {
            "model": self._model,
            # 稳定的判官指令放 system；OpenAI 兼容网关多会对前缀做自动缓存。
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        http_request = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                http_request, timeout=self._timeout
            ) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            raise LLMError(
                f"LLM request failed (HTTP {error.code}){_http_detail(error)}"
            ) from error
        except (urllib.error.URLError, OSError) as error:
            raise LLMError(f"LLM request failed: {error}") from error

        try:
            data = json.loads(raw)
            text = data["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
            raise LLMError(f"LLM response could not be parsed: {error}") from error

        if not isinstance(text, str):
            raise LLMError("LLM response did not contain text content")
        return LLMResponse(text=text)


def _http_detail(error: urllib.error.HTTPError) -> str:
    """尽力从 HTTP 错误体里取一小段可读原因，取不到就返回空串。"""

    try:
        body = error.read().decode("utf-8", "replace").strip()
    except Exception:  # pragma: no cover - 错误体不可读时安静退化。
        return ""
    if not body:
        return ""
    return f": {body[:_MAX_ERROR_DETAIL]}"
