from agentops.core.eval import VERDICT_DRIFT
from agentops.memory.trend import compute_score_trend
from agentops.parsers.history import HistoryRecord


def _record(score: int | None = None, *, drift: int = 0, timestamp: str = "t") -> HistoryRecord:
    """构造一条最小历史记录；可选地携带分数与 drift 裁决计数。"""

    result: dict[str, object] = {"findings": [], "intent_verdicts": []}
    if score is not None:
        result["score"] = score
    verdict_summary: dict[str, object] = {}
    if drift:
        verdict_summary = {"by_verdict": {VERDICT_DRIFT: drift}}
    return HistoryRecord(
        timestamp=timestamp, result=result, verdict_summary=verdict_summary
    )


def test_trend_is_unknown_for_zero_samples() -> None:
    trend = compute_score_trend(())

    assert trend.sample_count == 0
    assert trend.first_score is None
    assert trend.last_score is None
    assert trend.average_score is None
    assert trend.direction == "unknown"
    assert trend.drift_verdict_total == 0


def test_trend_is_unknown_for_single_sample() -> None:
    trend = compute_score_trend((_record(80),))

    assert trend.sample_count == 1
    assert trend.first_score == 80
    assert trend.last_score == 80
    assert trend.average_score == 80.0
    # 不足两条样本无法判断走向。
    assert trend.direction == "unknown"


def test_trend_direction_improving_worsening_flat() -> None:
    improving = compute_score_trend((_record(70), _record(90)))
    assert improving.direction == "improving"
    assert improving.first_score == 70
    assert improving.last_score == 90

    worsening = compute_score_trend((_record(90), _record(70)))
    assert worsening.direction == "worsening"

    flat = compute_score_trend((_record(80), _record(80)))
    assert flat.direction == "flat"


def test_trend_average_uses_fixed_rounding() -> None:
    trend = compute_score_trend((_record(70), _record(70), _record(71)))

    # round(211 / 3, 2) == 70.33，固定两位小数保证可复现。
    assert trend.average_score == 70.33


def test_trend_sums_drift_verdicts_across_records() -> None:
    trend = compute_score_trend(
        (
            _record(80, drift=1),
            _record(80, drift=2),
            _record(80),  # 无 drift
        )
    )

    assert trend.drift_verdict_total == 3


def test_trend_drift_total_is_zero_when_summary_absent() -> None:
    trend = compute_score_trend((_record(80), _record(80)))

    assert trend.drift_verdict_total == 0
