"""仓库记忆的确定性投影模块。

把累积的 eval-history.jsonl 蒸馏为趋势、失败模式、规则候选与 skill 候选，并在一个
可注入的叙述接缝后装配为 RepoMemory。本阶段叙述者只有确定性身份实现：同样的历史
产出字节一致的记忆，不触网、不需 key、无新增运行时依赖。
"""

from agentops.memory.aggregate import build_repo_memory
from agentops.memory.candidates import (
    derive_rule_candidates,
    derive_skill_candidates,
)
from agentops.memory.failure_modes import mine_failure_modes
from agentops.memory.narrator import DeterministicMemoryNarrator, MemoryNarrator
from agentops.memory.trend import compute_score_trend

__all__ = [
    "DeterministicMemoryNarrator",
    "MemoryNarrator",
    "build_repo_memory",
    "compute_score_trend",
    "derive_rule_candidates",
    "derive_skill_candidates",
    "mine_failure_modes",
]
