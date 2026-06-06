from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentops.core import ArtifactKind
from agentops.core.workflow import WorkflowEventType, WorkflowStatus
from agentops.memory import DeterministicMemoryNarrator
from agentops.runtime.memory import MemoryWorkflowError, run_memory


def _finding(code: str, evidence: tuple[str, ...]) -> dict[str, object]:
    return {
        "code": code,
        "severity": "warning",
        "message": "m",
        "evidence": list(evidence),
    }


def _history_line(
    timestamp: str,
    score: int,
    *,
    findings: tuple[dict[str, object], ...] = (),
    verdict_summary: dict[str, object] | None = None,
) -> str:
    record = {
        "timestamp": timestamp,
        "result": {
            "score": score,
            "findings": list(findings),
            "intent_verdicts": [],
        },
        "verdict_summary": verdict_summary if verdict_summary is not None else {},
    }
    return json.dumps(record, ensure_ascii=False, sort_keys=True)


def _write_history(tmp_path: Path, *lines: str) -> Path:
    history_path = tmp_path / ".agentops" / "eval-history.jsonl"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return history_path


def test_run_memory_orchestrates_pipeline_and_writes_artifacts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    history = _write_history(
        repo,
        _history_line(
            "t1", 85, findings=(_finding("undeclared_change", ("src/a.py",)),)
        ),
        _history_line(
            "t2", 80, findings=(_finding("undeclared_change", ("src/b.py",)),)
        ),
    )
    output_dir = tmp_path / "out"

    run = run_memory(repo, history, output_dir)

    assert run.memory.sample_count == 2
    assert run.memory.trend.direction == "worsening"  # 85 -> 80
    assert [mode.code for mode in run.memory.failure_modes] == ["undeclared_change"]
    assert run.memory.rule_candidates
    assert run.memory.skill_candidates
    assert run.trace.status is WorkflowStatus.COMPLETED
    assert [
        event.step_name
        for event in run.trace.events
        if event.event_type is WorkflowEventType.STEP_COMPLETED
    ] == ["read_history", "build_memory", "write_memory_artifacts"]
    assert {artifact.kind for artifact in run.artifacts} == {
        ArtifactKind.MEMORY_REPORT,
        ArtifactKind.MEMORY_JSON,
        ArtifactKind.SKILL_CANDIDATES,
        ArtifactKind.WORKFLOW_TRACE,
    }
    assert (output_dir / "agentops-memory.md").exists()
    assert (output_dir / "agentops-memory.json").exists()
    assert (output_dir / "skill-candidates.md").exists()
    assert (output_dir / "agentops-trace.json").exists()


def test_run_memory_uses_repo_path_as_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    history = _write_history(repo, _history_line("t1", 80))

    run = run_memory(repo, history, tmp_path / "out")

    assert run.memory.repo_root == str(repo)


def test_run_memory_single_record_yields_unknown_direction(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    history = _write_history(repo, _history_line("t1", 80))

    run = run_memory(repo, history, tmp_path / "out")

    assert run.memory.sample_count == 1
    assert run.memory.trend.direction == "unknown"


def test_run_memory_missing_history_raises_structured_error(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    output_dir = tmp_path / "out"

    with pytest.raises(MemoryWorkflowError) as exc_info:
        run_memory(repo, repo / ".agentops" / "eval-history.jsonl", output_dir)

    error = exc_info.value
    assert error.trace.status is WorkflowStatus.FAILED
    assert error.trace.failures[0].step_name == "read_history"
    # 缺失历史给出"先跑 agentops eval"的明确指引。
    assert "run agentops eval first" in error.trace.failures[0].message
    assert error.trace_artifact is not None
    assert (
        json.loads(error.trace_artifact.path.read_text(encoding="utf-8"))["status"]
        == "failed"
    )


def test_run_memory_empty_history_raises_structured_error(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    # 全是空行 / 坏行 → 零条可用记录。
    history = _write_history(repo, "", "   ", "not-json", "{}")

    with pytest.raises(MemoryWorkflowError) as exc_info:
        run_memory(repo, history, tmp_path / "out")

    assert exc_info.value.trace.failures[0].step_name == "read_history"
    assert "run agentops eval first" in exc_info.value.trace.failures[0].message


def test_run_memory_memory_artifacts_are_byte_identical_across_runs(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    history = _write_history(
        repo,
        _history_line(
            "t1", 90, findings=(_finding("undeclared_change", ("src/a.py",)),)
        ),
        _history_line(
            "t2", 90, findings=(_finding("undeclared_change", ("src/b.py",)),)
        ),
    )

    run_memory(repo, history, tmp_path / "one")
    run_memory(repo, history, tmp_path / "two")

    # 记忆是历史的确定性投影：三个记忆产物字节一致。
    # （trace 故意带随机 workflow_id 便于日志关联，不在此保证之内。）
    for name in ("agentops-memory.md", "agentops-memory.json", "skill-candidates.md"):
        assert (tmp_path / "one" / name).read_text(encoding="utf-8") == (
            tmp_path / "two" / name
        ).read_text(encoding="utf-8")


def test_run_memory_injected_timestamp_stamps_trace_events(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    history = _write_history(repo, _history_line("t1", 80), _history_line("t2", 90))
    fixed = datetime(2026, 6, 6, tzinfo=timezone.utc)

    run = run_memory(repo, history, tmp_path / "out", timestamp=fixed)

    # 注入的时间戳成为统一工作流时钟，让 trace 事件时间可复现。
    assert run.trace.events
    assert all(event.timestamp == fixed for event in run.trace.events)


def test_run_memory_default_narrator_matches_explicit_deterministic(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    history = _write_history(repo, _history_line("t1", 80), _history_line("t2", 70))

    default = run_memory(repo, history, tmp_path / "a")
    explicit = run_memory(
        repo, history, tmp_path / "b", narrator=DeterministicMemoryNarrator()
    )

    # 默认路径就是确定性身份叙述者：不触网、不需 key，结果与显式确定性 narrator 一致。
    assert default.memory == explicit.memory


def test_run_memory_overwrites_not_appends_on_second_run(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    history = _write_history(repo, _history_line("t1", 80), _history_line("t2", 90))
    output_dir = tmp_path / "out"

    run_memory(repo, history, output_dir)
    first = (output_dir / "agentops-memory.json").read_text(encoding="utf-8")
    run_memory(repo, history, output_dir)
    second = (output_dir / "agentops-memory.json").read_text(encoding="utf-8")

    # 记忆是历史的可再生投影：二次运行覆盖写、字节一致。
    assert first == second
