"""provider 无关的 LLM 接缝：文本进、文本出的最薄接口。

裁决（judge）需要语义判断，但不应把任何具体 provider 绑进核心流程。本模块只定义
一个 ``LLMClient`` 协议和两个 frozen 请求/响应载体，外加统一的 ``LLMError``。
结构化输出（严格 JSON 的解析与校验）是调用方（judge）的职责，这样接缝对任意
provider 都成立，且"响应无法解析"退化为一次安全降级而不是崩溃。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class LLMRequest:
    """一次裁决调用的 provider 无关请求。"""

    system: str
    user: str
    max_tokens: int = 1024
    temperature: float = 0.0  # 裁决要尽量可复现，温度取 0


@dataclass(frozen=True)
class LLMResponse:
    """provider 无关的文本响应；结构化解析交给调用方（judge）。"""

    text: str


class LLMError(RuntimeError):
    """统一封装所有 LLM 调用失败：缺 SDK、缺 key、网络、超时、provider 报错。"""


@runtime_checkable
class LLMClient(Protocol):
    """文本进、文本出的最薄接缝；具体 provider 由适配器实现。"""

    def complete(self, request: LLMRequest) -> LLMResponse: ...
