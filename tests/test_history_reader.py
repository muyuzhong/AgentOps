import json
from pathlib import Path

from agentops.parsers.history import (
    MAX_HISTORY_RECORDS,
    EvalHistoryReader,
    HistoryRecord,
)


def _history_file(tmp_path: Path, lines: list[str]) -> Path:
    """把若干行写入 .agentops/eval-history.jsonl 并返回其路径。"""

    path = tmp_path / ".agentops" / "eval-history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    return path


def _record_line(timestamp: str, score: int, *, with_summary: bool = True) -> str:
    """构造一条形态与 eval 流程写出一致的历史行。"""

    payload: dict[str, object] = {
        "timestamp": timestamp,
        "result": {"score": score, "findings": [], "intent_verdicts": []},
    }
    if with_summary:
        payload["verdict_summary"] = {
            "total": 0,
            "by_verdict": {},
            "by_source": {},
        }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def test_reads_wellformed_lines_in_source_order(tmp_path: Path) -> None:
    path = _history_file(
        tmp_path,
        [
            _record_line("2026-06-01T10:00:00", 70),
            _record_line("2026-06-02T10:00:00", 80),
            _record_line("2026-06-03T10:00:00", 90),
        ],
    )

    records = EvalHistoryReader().read(path)

    assert all(isinstance(record, HistoryRecord) for record in records)
    assert tuple(record.timestamp for record in records) == (
        "2026-06-01T10:00:00",
        "2026-06-02T10:00:00",
        "2026-06-03T10:00:00",
    )
    assert [record.result["score"] for record in records] == [70, 80, 90]
    assert records[0].verdict_summary == {
        "total": 0,
        "by_verdict": {},
        "by_source": {},
    }


def test_tolerates_pre_4_5_line_without_verdict_summary(tmp_path: Path) -> None:
    path = _history_file(
        tmp_path,
        [_record_line("2026-06-01T10:00:00", 70, with_summary=False)],
    )

    records = EvalHistoryReader().read(path)

    assert len(records) == 1
    # 4.5 之前的旧行没有 verdict_summary，回退为空摘要。
    assert records[0].verdict_summary == {}


def test_skips_blank_unparseable_and_resultless_lines(tmp_path: Path) -> None:
    path = _history_file(
        tmp_path,
        [
            "",
            "   ",
            "not json at all",
            json.dumps({"timestamp": "t", "verdict_summary": {}}),  # 缺 result
            json.dumps({"timestamp": "t", "result": "not-a-dict"}),  # result 非字典
            _record_line("2026-06-02T10:00:00", 80),
        ],
    )

    records = EvalHistoryReader().read(path)

    assert len(records) == 1
    assert records[0].result["score"] == 80


def test_returns_empty_tuple_for_empty_file(tmp_path: Path) -> None:
    path = _history_file(tmp_path, [])

    assert EvalHistoryReader().read(path) == ()


def test_is_bounded_to_newest_records_preserving_order(tmp_path: Path) -> None:
    total = MAX_HISTORY_RECORDS + 5
    lines = [
        json.dumps({"timestamp": f"t{index}", "result": {"score": 50}})
        for index in range(total)
    ]
    path = _history_file(tmp_path, lines)

    records = EvalHistoryReader().read(path)

    # 有界：只保留最新的 MAX_HISTORY_RECORDS 条，且维持源顺序。
    assert len(records) == MAX_HISTORY_RECORDS
    assert records[0].timestamp == "t5"
    assert records[-1].timestamp == f"t{total - 1}"
