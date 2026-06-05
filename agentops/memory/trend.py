"""跨评测的分数与漂移走向（确定性投影）。

只读 `result.score` 与历史行的 `verdict_summary`，给出 first/last/average 分数、
走向（improving / worsening / flat / unknown）和累积 drift 裁决数。绝不重算、扣减
或写回任何评测分数——走向是只读洞察，是否让漂移校准分数留待后续依累积数据再定。
"""

from __future__ import annotations

from agentops.core.eval import VERDICT_DRIFT
from agentops.core.memory import ScoreTrend
from agentops.parsers.history import HistoryRecord

# 平均分固定保留的小数位数：固定舍入保证同样历史得到字节一致的结果。
_AVERAGE_DECIMALS = 2


def compute_score_trend(records: tuple[HistoryRecord, ...]) -> ScoreTrend:
    """把历史记录确定性地投影为 ScoreTrend。"""

    scores = [score for record in records if (score := _score_of(record)) is not None]
    drift_total = sum(_drift_count(record) for record in records)

    if not scores:
        return ScoreTrend(
            sample_count=0,
            first_score=None,
            last_score=None,
            average_score=None,
            direction="unknown",
            drift_verdict_total=drift_total,
        )

    return ScoreTrend(
        sample_count=len(scores),
        first_score=scores[0],
        last_score=scores[-1],
        average_score=round(sum(scores) / len(scores), _AVERAGE_DECIMALS),
        direction=_direction(scores),
        drift_verdict_total=drift_total,
    )


def _score_of(record: HistoryRecord) -> int | None:
    """取出一条记录的整数分数；缺失或类型异常（含 bool）时返回 None。"""

    score = record.result.get("score")
    if isinstance(score, bool):
        return None
    return score if isinstance(score, int) else None


def _direction(scores: list[int]) -> str:
    """按"最早 vs 最近"的固定规则给出走向；不足两条样本为 unknown。"""

    if len(scores) < 2:
        return "unknown"
    first, last = scores[0], scores[-1]
    if last > first:
        return "improving"
    if last < first:
        return "worsening"
    return "flat"


def _drift_count(record: HistoryRecord) -> int:
    """从历史行的 verdict_summary.by_verdict 取 drift 计数；缺失或异常时记 0。"""

    by_verdict = record.verdict_summary.get("by_verdict", {})
    if not isinstance(by_verdict, dict):
        return 0
    count = by_verdict.get(VERDICT_DRIFT, 0)
    if isinstance(count, bool):
        return 0
    return count if isinstance(count, int) else 0
