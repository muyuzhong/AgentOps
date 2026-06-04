"""provider 无关的 LLM 接缝与适配器。"""

from agentops.llm.client import LLMClient, LLMError, LLMRequest, LLMResponse
from agentops.llm.openai_compatible import OpenAICompatibleClient

__all__ = [
    "LLMClient",
    "LLMError",
    "LLMRequest",
    "LLMResponse",
    "OpenAICompatibleClient",
]
