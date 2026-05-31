from pathlib import Path

import pytest

import agentops.core as core
from agentops.core.evidence import (
    CIProfile,
    ChangeKind,
    ChangedFile,
    DiffSummary,
    GitStatus,
    ShellResult,
    TestResult as EvidenceTestResult,
)


def test_diff_summary_serializes_changed_files() -> None:
    summary = DiffSummary(
        files=(
            ChangedFile(
                path="src/app.py",
                change_kind=ChangeKind.MODIFIED,
                additions=3,
                deletions=1,
            ),
        ),
        additions=3,
        deletions=1,
    )

    assert summary.to_dict() == {
        "files": [
            {
                "path": "src/app.py",
                "change_kind": "modified",
                "additions": 3,
                "deletions": 1,
                "previous_path": None,
            },
        ],
        "additions": 3,
        "deletions": 1,
    }


def test_git_status_serializes_paths_and_optional_branch() -> None:
    status = GitStatus(
        repo_root=Path("demo"),
        branch=None,
        changed_paths=("src/app.py",),
        untracked_paths=("notes.txt",),
    )

    assert status.to_dict() == {
        "repo_root": "demo",
        "branch": None,
        "changed_paths": ["src/app.py"],
        "untracked_paths": ["notes.txt"],
    }


def test_ci_profile_serializes_detected_evidence() -> None:
    profile = CIProfile(
        config_files=(".github/workflows/test.yml",),
        validation_commands=("python -m pytest",),
    )

    assert profile.to_dict() == {
        "config_files": [".github/workflows/test.yml"],
        "validation_commands": ["python -m pytest"],
    }


def test_shell_result_serializes_nested_test_result() -> None:
    result = ShellResult(
        command="python -m pytest",
        exit_code=1,
        succeeded=False,
        summary="1 failed, 2 passed",
        truncated=False,
        test_result=EvidenceTestResult(
            framework="pytest",
            passed=2,
            failed=1,
            skipped=0,
            errors=0,
            succeeded=False,
        ),
    )

    assert result.to_dict() == {
        "command": "python -m pytest",
        "exit_code": 1,
        "succeeded": False,
        "summary": "1 failed, 2 passed",
        "truncated": False,
        "test_result": {
            "framework": "pytest",
            "passed": 2,
            "failed": 1,
            "skipped": 0,
            "errors": 0,
            "succeeded": False,
        },
    }


def test_shell_result_serializes_unknown_test_result_defaults() -> None:
    result = ShellResult(
        command="custom-test",
        exit_code=0,
        succeeded=True,
        summary="unsupported output",
        test_result=EvidenceTestResult(framework="unknown"),
    )

    assert result.to_dict() == {
        "command": "custom-test",
        "exit_code": 0,
        "succeeded": True,
        "summary": "unsupported output",
        "truncated": False,
        "test_result": {
            "framework": "unknown",
            "passed": None,
            "failed": None,
            "skipped": None,
            "errors": None,
            "succeeded": None,
        },
    }


def test_shell_result_serializes_absent_test_result() -> None:
    result = ShellResult(
        command="custom-test",
        exit_code=0,
        succeeded=True,
        summary="unsupported output",
    )

    assert result.to_dict()["test_result"] is None


def test_core_exports_public_evidence_types() -> None:
    assert core.CIProfile is CIProfile
    assert core.ChangeKind is ChangeKind
    assert core.ChangedFile is ChangedFile
    assert core.DiffSummary is DiffSummary
    assert core.GitStatus is GitStatus
    assert core.ShellResult is ShellResult
    assert core.TestResult is EvidenceTestResult


@pytest.mark.parametrize("field", ["additions", "deletions"])
def test_changed_file_rejects_negative_line_counts(field: str) -> None:
    values = {"additions": 0, "deletions": 0}
    values[field] = -1

    with pytest.raises(ValueError, match="line counts must be non-negative"):
        ChangedFile(
            path="src/app.py",
            change_kind=ChangeKind.MODIFIED,
            **values,
        )


@pytest.mark.parametrize("count", [True, 1.5])
def test_changed_file_rejects_non_integer_line_counts(count: object) -> None:
    with pytest.raises(ValueError, match="line counts must be non-negative"):
        ChangedFile(
            path="src/app.py",
            change_kind=ChangeKind.MODIFIED,
            additions=count,
            deletions=0,
        )


@pytest.mark.parametrize("field", ["additions", "deletions"])
def test_diff_summary_rejects_negative_line_counts(field: str) -> None:
    values = {"additions": 0, "deletions": 0}
    values[field] = -1

    with pytest.raises(ValueError, match="line counts must be non-negative"):
        DiffSummary(files=(), **values)


@pytest.mark.parametrize("field", ["passed", "failed", "skipped", "errors"])
def test_test_result_rejects_negative_counts(field: str) -> None:
    values = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
    }
    values[field] = -1

    with pytest.raises(ValueError, match="test counts must be non-negative"):
        EvidenceTestResult(framework="pytest", succeeded=False, **values)


@pytest.mark.parametrize("count", [True, 1.5])
def test_test_result_rejects_non_integer_counts(count: object) -> None:
    with pytest.raises(ValueError, match="test counts must be non-negative"):
        EvidenceTestResult(framework="pytest", passed=count)
