from dataclasses import FrozenInstanceError
from pathlib import Path

import agentops.core as core
import pytest
from agentops.core.session import SessionTrace, TaskReport, VerificationRecord


def test_session_trace_serializes_bounded_task_reports(tmp_path: Path) -> None:
    trace = SessionTrace(
        source_path=tmp_path / ".agentops" / "agentops-session.md",
        tasks=(
            TaskReport(
                title="Fix login error",
                goal="Return 401 for expired tokens.",
                context_used=("src/auth.py",),
                changes=("Adjust expired-token mapping.",),
                verification=(
                    VerificationRecord(
                        command="python -m pytest tests/test_auth.py -v",
                        result="3 passed",
                    ),
                ),
                evidence_references=("Transcript: evt_018-evt_031",),
            ),
        ),
    )

    assert trace.to_dict() == {
        "source_path": str(tmp_path / ".agentops" / "agentops-session.md"),
        "tasks": [
            {
                "title": "Fix login error",
                "goal": "Return 401 for expired tokens.",
                "context_used": ["src/auth.py"],
                "changes": ["Adjust expired-token mapping."],
                "changed_files": [],
                "verification": [
                    {
                        "command": "python -m pytest tests/test_auth.py -v",
                        "result": "3 passed",
                    },
                ],
                "issues": [],
                "evidence_references": ["Transcript: evt_018-evt_031"],
                "truncated": False,
            },
        ],
        "truncated": False,
    }


def test_task_report_serializes_optional_lists_and_truncation() -> None:
    report = TaskReport(
        title="Keep evidence bounded",
        goal="Expose parser-ready task evidence.",
        context_used=("agentops/core/session.py",),
        changes=("Add immutable models.",),
        issues=("Retained only bounded evidence.",),
        truncated=True,
    )

    assert report.to_dict() == {
        "title": "Keep evidence bounded",
        "goal": "Expose parser-ready task evidence.",
        "context_used": ["agentops/core/session.py"],
        "changes": ["Add immutable models."],
        "changed_files": [],
        "verification": [],
        "issues": ["Retained only bounded evidence."],
        "evidence_references": [],
        "truncated": True,
    }


def test_task_report_serializes_changed_files() -> None:
    report = TaskReport(
        title="Declare changed files",
        goal="Make declared paths explicit.",
        changes=("Add changed_files field.",),
        changed_files=("agentops/core/session.py", "tests/test_session_models.py"),
    )

    assert report.to_dict() == {
        "title": "Declare changed files",
        "goal": "Make declared paths explicit.",
        "context_used": [],
        "changes": ["Add changed_files field."],
        "changed_files": [
            "agentops/core/session.py",
            "tests/test_session_models.py",
        ],
        "verification": [],
        "issues": [],
        "evidence_references": [],
        "truncated": False,
    }


def test_session_trace_serializes_empty_tasks_and_truncation(tmp_path: Path) -> None:
    trace = SessionTrace(
        source_path=tmp_path / ".agentops" / "agentops-session.md",
        tasks=(),
        truncated=True,
    )

    assert trace.to_dict() == {
        "source_path": str(tmp_path / ".agentops" / "agentops-session.md"),
        "tasks": [],
        "truncated": True,
    }


def test_core_exports_public_session_types() -> None:
    assert core.SessionTrace is SessionTrace
    assert core.TaskReport is TaskReport
    assert core.VerificationRecord is VerificationRecord


@pytest.mark.parametrize(
    ("model", "field", "value"),
    [
        (VerificationRecord(command="pytest", result="1 passed"), "result", "failed"),
        (TaskReport(title="Task", goal="Goal"), "truncated", True),
        (SessionTrace(source_path=Path("session.md"), tasks=()), "truncated", True),
    ],
)
def test_session_models_are_immutable(model: object, field: str, value: object) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(model, field, value)
