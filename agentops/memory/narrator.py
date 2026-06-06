"""记忆叙述接缝：把确定性投影富化为更可读的失败模式 / skill 描述。

Phase 5 只提供确定性默认实现（身份变换）。LLM 叙述者留到后续可选切片（Phase 5.5）
按同一接口填充，且**只能改写描述字段**（summary / rationale / title），绝不改动结构
事实（code / 计数 / 路径）——与 LLM 意图判官"绝不重新推导文件集合"同构。

接缝先就位、可注入，但本阶段唯一行为是确定性：``DeterministicMemoryNarrator`` 直接
返回投影，不改写、不触网、不需 key。填充 LLM 叙述者不得改变接缝形状。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from agentops.core.memory import RepoMemory


@runtime_checkable
class MemoryNarrator(Protocol):
    """把确定性 RepoMemory 投影富化为更可读描述的可注入接口。"""

    def narrate(self, memory: RepoMemory) -> RepoMemory:
        """返回（可能富化了描述字段的）记忆；结构事实必须保持不变。"""


class DeterministicMemoryNarrator:
    """默认叙述者：直接返回确定性模板投影，不改写、不触网、不需 key。"""

    def narrate(self, memory: RepoMemory) -> RepoMemory:
        """身份变换：原样返回投影。"""

        return memory
