"""仓库记忆的确定性投影模块。

把累积的 eval-history.jsonl 蒸馏为趋势、失败模式、规则候选与 skill 候选。本阶段
先提供确定性的趋势与失败模式挖掘；投影装配与叙述接缝在后续任务接入此包。
"""

from agentops.memory.failure_modes import mine_failure_modes
from agentops.memory.trend import compute_score_trend

__all__ = [
    "compute_score_trend",
    "mine_failure_modes",
]
