"""跨评测反复出现的失败模式挖掘（确定性投影）。

把历史里 `result.findings[].code` 按三个稳定的 scope code 聚类，并从
`result.intent_verdicts[]` 中 verdict == drift 的裁决额外派生 confirmed_drift
（信号最强、由 LLM 确认的模式）。每个模式带 N/M 复现证据、热点路径与最近出现时间，
按出现次数降序、code 升序排列。聚类只数客观事实，叙述富化留给后续的叙述接缝。
"""

from __future__ import annotations

from agentops.core.eval import VERDICT_DRIFT
from agentops.core.memory import FailureMode
from agentops.parsers.history import HistoryRecord

# 纳入聚类的三个稳定 scope code（intent_alignment 只是 LLM 插入标记，不是失败模式）。
SCOPE_CODES = ("undeclared_change", "declared_not_changed", "cross_module_breadth")

# 由 drift 意图裁决派生的失败模式 code。
CONFIRMED_DRIFT = "confirmed_drift"

# 每个模式保留的热点路径上限（结果有界）。
MAX_HOT_PATHS = 10


def mine_failure_modes(records: tuple[HistoryRecord, ...]) -> tuple[FailureMode, ...]:
    """把历史记录确定性地投影为按出现次数排序的失败模式。"""

    sample_count = len(records)
    occurrence: dict[str, int] = {}
    path_counts: dict[str, dict[str, int]] = {}
    last_seen: dict[str, str] = {}

    for record in records:
        for code, paths in _codes_in_record(record).items():
            occurrence[code] = occurrence.get(code, 0) + 1
            counts = path_counts.setdefault(code, {})
            for path in paths:
                counts[path] = counts.get(path, 0) + 1
            # 源顺序即时间顺序：后出现的记录覆盖更新 last_seen。
            last_seen[code] = record.timestamp

    modes: list[FailureMode] = []
    for code, count in occurrence.items():
        hot_paths = _rank_hot_paths(path_counts.get(code, {}))
        modes.append(
            FailureMode(
                code=code,
                occurrence_count=count,
                sample_count=sample_count,
                hot_paths=hot_paths,
                last_seen=last_seen.get(code, ""),
                summary=_summary(code, count, sample_count, hot_paths),
            )
        )

    # 出现次数降序、code 升序——确定性排序，同样历史得到同样顺序。
    modes.sort(key=lambda mode: (-mode.occurrence_count, mode.code))
    return tuple(modes)


def _codes_in_record(record: HistoryRecord) -> dict[str, list[str]]:
    """返回本条记录贡献的 {失败模式 code: 证据路径列表}（每个 code 至多一项）。"""

    result = record.result
    codes: dict[str, list[str]] = {}

    findings = result.get("findings", [])
    if isinstance(findings, list):
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            code = finding.get("code")
            if code in SCOPE_CODES:
                codes.setdefault(code, []).extend(_evidence_of(finding))

    verdicts = result.get("intent_verdicts", [])
    if isinstance(verdicts, list):
        for verdict in verdicts:
            if not isinstance(verdict, dict):
                continue
            if verdict.get("verdict") == VERDICT_DRIFT:
                codes.setdefault(CONFIRMED_DRIFT, []).extend(_evidence_of(verdict))

    return codes


def _evidence_of(item: dict[str, object]) -> list[str]:
    """取出一条发现/裁决里的字符串证据；类型异常时安全跳过。"""

    evidence = item.get("evidence", [])
    if not isinstance(evidence, list):
        return []
    return [value for value in evidence if isinstance(value, str)]


def _rank_hot_paths(counts: dict[str, int]) -> tuple[str, ...]:
    """按频次降序、路径升序排列热点路径，并截断到上限。"""

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return tuple(path for path, _ in ranked[:MAX_HOT_PATHS])


def _summary(
    code: str,
    occurrence_count: int,
    sample_count: int,
    hot_paths: tuple[str, ...],
) -> str:
    """确定性模板摘要：带 N/M 复现证据与热点路径（叙述接缝可后续富化）。"""

    paths = ", ".join(hot_paths) if hot_paths else "none"
    return (
        f"'{code}' recurred in {occurrence_count}/{sample_count} evals; "
        f"hot paths: {paths}."
    )
