from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentops.core import ArtifactKind
from agentops.core.workflow import WorkflowEventType, WorkflowStatus
from agentops.runtime.improve import ImproveWorkflowError, run_suggest


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
) -> str:
    record = {
        "timestamp": timestamp,
        "result": {
            "score": score,
            "findings": list(findings),
            "intent_verdicts": [],
        },
        "verdict_summary": {},
    }
    return json.dumps(record, ensure_ascii=False, sort_keys=True)


def _write_history(tmp_path: Path, *lines: str) -> Path:
    history_path = tmp_path / ".agentops" / "eval-history.jsonl"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return history_path


def test_run_suggest_orchestrates_pipeline_and_writes_artifacts(tmp_path: Path) -> None:
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

    run = run_suggest(repo, history, output_dir)

    assert run.assets.sample_count == 2
    assert [s.target for s in run.assets.instruction_suggestions] == [
        "CLAUDE.md",
        "AGENTS.md",
    ]
    # undeclared_change @ 2/2 复现 → 一条 hook 提案。
    assert run.assets.hook_proposals
    assert run.trace.status is WorkflowStatus.COMPLETED
    assert [
        event.step_name
        for event in run.trace.events
        if event.event_type is WorkflowEventType.STEP_COMPLETED
    ] == [
        "read_history",
        "build_memory",
        "read_instructions",
        "build_assets",
        "write_improvement_artifacts",
    ]
    assert {artifact.kind for artifact in run.artifacts} == {
        ArtifactKind.SUGGESTED_CLAUDE_MD,
        ArtifactKind.SUGGESTED_AGENTS_MD,
        ArtifactKind.HOOK_PROPOSALS,
        ArtifactKind.SUGGESTIONS_JSON,
        ArtifactKind.WORKFLOW_TRACE,
    }
    for name in (
        "suggested-claude-md.md",
        "suggested-agents-md.md",
        "suggested-hooks.md",
        "agentops-suggestions.json",
        "agentops-trace.json",
    ):
        assert (output_dir / name).exists()


def test_run_suggest_reads_instructions_read_only(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    history = _write_history(repo, _history_line("t1", 80), _history_line("t2", 70))
    claude = repo / "CLAUDE.md"
    agents = repo / "AGENTS.md"
    readme = repo / "README.md"
    claude.write_text("# rules\n", encoding="utf-8")
    agents.write_text("# agents\n", encoding="utf-8")
    readme.write_text("# Project\n\nIntro.\n", encoding="utf-8")
    before = (
        claude.read_text(encoding="utf-8"),
        agents.read_text(encoding="utf-8"),
        readme.read_text(encoding="utf-8"),
    )

    run_suggest(repo, history, tmp_path / "out")

    # 目标仓库的指令文件只读：运行后内容不变。
    assert (
        claude.read_text(encoding="utf-8"),
        agents.read_text(encoding="utf-8"),
        readme.read_text(encoding="utf-8"),
    ) == before


def test_run_suggest_missing_history_raises_structured_error(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    output_dir = tmp_path / "out"

    with pytest.raises(ImproveWorkflowError) as exc_info:
        run_suggest(repo, repo / ".agentops" / "eval-history.jsonl", output_dir)

    error = exc_info.value
    assert error.trace.status is WorkflowStatus.FAILED
    assert error.trace.failures[0].step_name == "read_history"
    # 缺失历史给出“先跑 agentops eval”的明确指引。
    assert "run agentops eval first" in error.trace.failures[0].message
    assert error.trace_artifact is not None
    assert (
        json.loads(error.trace_artifact.path.read_text(encoding="utf-8"))["status"]
        == "failed"
    )


def test_run_suggest_empty_history_raises_structured_error(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    # 全是空行 / 坏行 → 零条可用记录。
    history = _write_history(repo, "", "   ", "not-json", "{}")

    with pytest.raises(ImproveWorkflowError) as exc_info:
        run_suggest(repo, history, tmp_path / "out")

    assert exc_info.value.trace.failures[0].step_name == "read_history"
    assert "run agentops eval first" in exc_info.value.trace.failures[0].message


def test_run_suggest_artifacts_are_byte_identical_across_runs(tmp_path: Path) -> None:
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

    run_suggest(repo, history, tmp_path / "one")
    run_suggest(repo, history, tmp_path / "two")

    # 资产是历史 + 指令文件的确定性投影：四个资产产物字节一致。
    # （trace 故意带随机 workflow_id 便于日志关联，不在此保证之内。）
    for name in (
        "suggested-claude-md.md",
        "suggested-agents-md.md",
        "suggested-hooks.md",
        "agentops-suggestions.json",
    ):
        assert (tmp_path / "one" / name).read_text(encoding="utf-8") == (
            tmp_path / "two" / name
        ).read_text(encoding="utf-8")


def test_run_suggest_injected_timestamp_stamps_trace_events(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    history = _write_history(repo, _history_line("t1", 80), _history_line("t2", 90))
    fixed = datetime(2026, 6, 7, tzinfo=timezone.utc)

    run = run_suggest(repo, history, tmp_path / "out", timestamp=fixed)

    # 注入的时间戳成为统一工作流时钟，让 trace 事件时间可复现。
    assert run.trace.events
    assert all(event.timestamp == fixed for event in run.trace.events)
