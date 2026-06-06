"""把累积的历史记录装配为 RepoMemory 投影（确定性，叙述接缝可注入）。

build_repo_memory 是仓库记忆的装配点：顺序调用各确定性投影函数——趋势、失败模式、
规则候选、skill 候选——组成一个 ``RepoMemory``，再交给可注入的 ``MemoryNarrator``
做描述富化。默认叙述者是确定性身份实现：同样的 records 产出字节一致的 RepoMemory，
不触网、不需 key。叙述者只能改写描述字段，绝不改动结构事实（code / 计数 / 路径）。
"""

from __future__ import annotations

from agentops.core.memory import RepoMemory
from agentops.memory.candidates import (
    derive_rule_candidates,
    derive_skill_candidates,
)
from agentops.memory.failure_modes import mine_failure_modes
from agentops.memory.narrator import DeterministicMemoryNarrator, MemoryNarrator
from agentops.memory.trend import compute_score_trend
from agentops.parsers.history import HistoryRecord


def build_repo_memory(
    records: tuple[HistoryRecord, ...],
    *,
    repo_root: str,
    narrator: MemoryNarrator | None = None,
) -> RepoMemory:
    """把历史记录确定性地投影为 RepoMemory；narrator 默认确定性身份实现。"""

    modes = mine_failure_modes(records)
    memory = RepoMemory(
        repo_root=repo_root,
        # M = 历史窗口里的评测总数（与各 FailureMode.sample_count 一致）。
        sample_count=len(records),
        trend=compute_score_trend(records),
        failure_modes=modes,
        rule_candidates=derive_rule_candidates(modes),
        skill_candidates=derive_skill_candidates(modes, records),
    )

    # 默认走确定性身份叙述者：投影原样返回，不触网、不需 key。
    chosen = narrator if narrator is not None else DeterministicMemoryNarrator()
    return chosen.narrate(memory)
