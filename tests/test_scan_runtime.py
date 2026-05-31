import json
from pathlib import Path

import pytest

from agentops.core.workflow import WorkflowEventType, WorkflowStatus
from agentops.runtime import scan as scan_runtime
from agentops.runtime.scan import run_scan
from agentops.writers.report import ReportWriter
from agentops.writers.trace import TraceWriter


def tree_snapshot(root: Path) -> tuple[tuple[str, bytes | None], ...]:
    return tuple(
        sorted(
            (
                path.relative_to(root).as_posix(),
                None if path.is_dir() else path.read_bytes(),
            )
            for path in root.rglob("*")
        )
    )


def test_run_scan_orchestrates_repository_readiness_workflow(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "README.md").write_text("# Demo", encoding="utf-8")
    (repo_path / "AGENTS.md").write_text("# Instructions", encoding="utf-8")
    (repo_path / "tests").mkdir()
    workflows_path = repo_path / ".github" / "workflows"
    workflows_path.mkdir(parents=True)
    (workflows_path / "ci.yml").write_text("name: CI", encoding="utf-8")
    (repo_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
    output_dir = tmp_path / "output"

    result = run_scan(repo_path, output_dir)

    assert result.report.profile.root == repo_path
    assert result.report.score == 100
    assert {item.path.name for item in result.artifacts} == {
        "agentops-report.md",
        "agentops-score.json",
        "agentops-trace.json",
    }
    assert result.trace.status is WorkflowStatus.COMPLETED
    assert [
        event.step_name
        for event in result.trace.events
        if event.event_type is WorkflowEventType.STEP_COMPLETED
    ] == [
        "scan_repository",
        "evaluate_readiness",
        "write_readiness_artifacts",
    ]
    assert json.loads((output_dir / "agentops-trace.json").read_text(encoding="utf-8"))[
        "status"
    ] == "completed"


def test_run_scan_keeps_target_repository_read_only_and_output_stable(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "README.md").write_text("# 演示仓库", encoding="utf-8")
    output_dir = tmp_path / "output"
    before_tree = tree_snapshot(repo_path)

    run_scan(repo_path, output_dir)
    first_markdown = (output_dir / "agentops-report.md").read_bytes()
    first_json = (output_dir / "agentops-score.json").read_bytes()
    run_scan(repo_path, output_dir)

    assert tree_snapshot(repo_path) == before_tree
    assert (output_dir / "agentops-report.md").read_bytes() == first_markdown
    assert (output_dir / "agentops-score.json").read_bytes() == first_json


def test_run_scan_preserves_trace_after_required_step_failure(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"

    with pytest.raises(scan_runtime.ScanWorkflowError) as exc_info:
        run_scan(tmp_path / "missing", output_dir)

    error = exc_info.value
    assert error.trace.status is WorkflowStatus.FAILED
    assert error.trace.failures[0].step_name == "scan_repository"
    assert error.trace_artifact is not None
    assert error.trace_artifact.path == output_dir / "agentops-trace.json"
    assert json.loads(error.trace_artifact.path.read_text(encoding="utf-8"))[
        "status"
    ] == "failed"
    assert not (output_dir / "agentops-report.md").exists()
    assert not (output_dir / "agentops-score.json").exists()


def test_run_scan_keeps_original_failure_when_trace_cannot_be_written(
    tmp_path: Path,
) -> None:
    output_file = tmp_path / "output"
    output_file.write_text("not a directory", encoding="utf-8")

    with pytest.raises(scan_runtime.ScanWorkflowError) as exc_info:
        run_scan(tmp_path / "missing", output_file)

    error = exc_info.value
    assert error.trace.failures[0].step_name == "scan_repository"
    assert error.trace_artifact is None


def test_run_scan_propagates_trace_writer_failure_after_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    def fail_trace_write(
        writer: TraceWriter, trace: object, output_dir: Path
    ) -> object:
        raise OSError("trace write failed")

    monkeypatch.setattr(TraceWriter, "write", fail_trace_write)

    with pytest.raises(OSError, match="trace write failed"):
        run_scan(repo_path, tmp_path / "output")


def test_run_scan_preserves_report_writer_failure_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    output_dir = tmp_path / "output"

    def fail_report_write(
        writer: ReportWriter, report: object, output_dir: Path
    ) -> object:
        raise OSError("report write failed")

    monkeypatch.setattr(ReportWriter, "write", fail_report_write)

    with pytest.raises(scan_runtime.ScanWorkflowError) as exc_info:
        run_scan(repo_path, output_dir)

    error = exc_info.value
    assert error.trace.failures[0].step_name == "write_readiness_artifacts"
    assert error.trace_artifact is not None
    assert json.loads(error.trace_artifact.path.read_text(encoding="utf-8"))[
        "status"
    ] == "failed"
