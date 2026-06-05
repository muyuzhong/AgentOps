from agentops.core.eval import VERDICT_DRIFT
from agentops.memory.failure_modes import (
    CONFIRMED_DRIFT,
    MAX_HOT_PATHS,
    mine_failure_modes,
)
from agentops.parsers.history import HistoryRecord


def _finding(code: str, evidence: tuple[str, ...]) -> dict[str, object]:
    return {
        "code": code,
        "severity": "warning",
        "message": "m",
        "evidence": list(evidence),
    }


def _verdict(verdict: str, evidence: tuple[str, ...]) -> dict[str, object]:
    return {
        "finding_code": "intent_alignment",
        "evidence": list(evidence),
        "verdict": verdict,
        "rationale": "r",
        "source": "llm",
    }


def _record(
    timestamp: str,
    *,
    findings: tuple[dict[str, object], ...] = (),
    verdicts: tuple[dict[str, object], ...] = (),
) -> HistoryRecord:
    return HistoryRecord(
        timestamp=timestamp,
        result={
            "score": 80,
            "findings": list(findings),
            "intent_verdicts": list(verdicts),
        },
        verdict_summary={},
    )


def test_clusters_scope_codes_by_occurrence_across_evals() -> None:
    records = (
        _record("t1", findings=(_finding("undeclared_change", ("src/a.py",)),)),
        _record("t2", findings=(_finding("undeclared_change", ("src/b.py",)),)),
        _record("t3", findings=(_finding("declared_not_changed", ("src/c.py",)),)),
    )

    by_code = {mode.code: mode for mode in mine_failure_modes(records)}

    # occurrence_count = 出现该模式的评测次数（N）；sample_count = 窗口内评测总数（M）。
    assert by_code["undeclared_change"].occurrence_count == 2
    assert by_code["undeclared_change"].sample_count == 3
    assert by_code["declared_not_changed"].occurrence_count == 1
    assert by_code["declared_not_changed"].sample_count == 3


def test_same_code_twice_in_one_eval_counts_as_one_occurrence() -> None:
    records = (
        _record(
            "t1",
            findings=(
                _finding("undeclared_change", ("src/a.py",)),
                _finding("undeclared_change", ("src/b.py",)),
            ),
        ),
    )

    by_code = {mode.code: mode for mode in mine_failure_modes(records)}

    # 一次评测里出现两条同 code 发现，仍只记一次出现，但热点路径都被收集。
    assert by_code["undeclared_change"].occurrence_count == 1
    assert by_code["undeclared_change"].hot_paths == ("src/a.py", "src/b.py")


def test_derives_confirmed_drift_from_drift_verdicts() -> None:
    records = (
        _record("t1", verdicts=(_verdict(VERDICT_DRIFT, ("src/x.py",)),)),
        _record("t2", verdicts=(_verdict("within_intent", ("src/y.py",)),)),  # 非 drift
    )

    by_code = {mode.code: mode for mode in mine_failure_modes(records)}

    assert CONFIRMED_DRIFT in by_code
    assert by_code[CONFIRMED_DRIFT].occurrence_count == 1
    assert by_code[CONFIRMED_DRIFT].hot_paths == ("src/x.py",)


def test_ranks_by_occurrence_desc_then_code_asc() -> None:
    records = (
        _record(
            "t1",
            findings=(
                _finding("undeclared_change", ("a",)),
                _finding("cross_module_breadth", ("m1", "m2", "m3")),
            ),
        ),
        _record(
            "t2",
            findings=(
                _finding("undeclared_change", ("b",)),
                _finding("cross_module_breadth", ("m1", "m2", "m3")),
            ),
        ),
        _record("t3", findings=(_finding("undeclared_change", ("c",)),)),
    )

    modes = mine_failure_modes(records)

    # undeclared_change 出现 3 次、cross_module_breadth 2 次 → 前者排前。
    assert [mode.code for mode in modes] == [
        "undeclared_change",
        "cross_module_breadth",
    ]


def test_ranks_ties_by_code_ascending() -> None:
    records = (
        _record(
            "t1",
            findings=(
                _finding("undeclared_change", ("a",)),
                _finding("declared_not_changed", ("b",)),
            ),
        ),
    )

    modes = mine_failure_modes(records)

    # 同为出现一次时按 code 升序：declared_not_changed < undeclared_change。
    assert [mode.code for mode in modes] == [
        "declared_not_changed",
        "undeclared_change",
    ]


def test_hot_paths_ranked_by_frequency_then_path_and_bounded() -> None:
    total = MAX_HOT_PATHS + 5
    records = tuple(
        _record(
            f"t{index}",
            findings=(_finding("undeclared_change", ("hot.py", f"u{index:03d}.py")),),
        )
        for index in range(total)
    )

    mode = next(m for m in mine_failure_modes(records) if m.code == "undeclared_change")

    # 频次最高的路径排在最前，结果数量有界。
    assert mode.hot_paths[0] == "hot.py"
    assert len(mode.hot_paths) == MAX_HOT_PATHS


def test_last_seen_is_newest_timestamp_per_mode() -> None:
    records = (
        _record("2026-06-01", findings=(_finding("undeclared_change", ("a",)),)),
        _record("2026-06-02", findings=(_finding("declared_not_changed", ("b",)),)),
        _record("2026-06-03", findings=(_finding("undeclared_change", ("c",)),)),
    )

    by_code = {mode.code: mode for mode in mine_failure_modes(records)}

    assert by_code["undeclared_change"].last_seen == "2026-06-03"
    assert by_code["declared_not_changed"].last_seen == "2026-06-02"


def test_summary_cites_recurrence() -> None:
    records = (
        _record("t1", findings=(_finding("undeclared_change", ("a",)),)),
        _record("t2", findings=(_finding("undeclared_change", ("b",)),)),
    )

    mode = mine_failure_modes(records)[0]

    # 确定性模板摘要至少要带上 N/M 复现证据。
    assert "2/2" in mode.summary
    assert mode.code in mode.summary


def test_no_modes_without_scope_findings_or_drift() -> None:
    records = (
        _record("t1", findings=(_finding("intent_alignment", ("x",)),)),  # 非 scope code
        _record("t2", verdicts=(_verdict("needs_review", ("y",)),)),  # 非 drift
    )

    assert mine_failure_modes(records) == ()
