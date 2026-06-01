from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import agentops.analyzers.git as git_module
from agentops.analyzers.git import GitAnalysisError, GitAnalyzer
from agentops.core import ChangeKind


def _run_git(repo_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """在测试仓库内执行 git，并在失败时立即暴露 stderr。"""

    return subprocess.run(
        ["git", *args],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        shell=False,
    )


def _create_git_repo(tmp_path: Path) -> Path:
    """创建含一个基线提交的临时 Git 仓库。"""

    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    _run_git(repo_path, "init")
    _run_git(repo_path, "config", "user.email", "agentops@example.com")
    _run_git(repo_path, "config", "user.name", "AgentOps Test")
    (repo_path / "tracked.txt").write_text("before\n", encoding="utf-8")
    _run_git(repo_path, "add", "tracked.txt")
    _run_git(repo_path, "commit", "-m", "baseline")
    return repo_path


def test_git_analyzer_collects_sorted_status_paths(tmp_path: Path) -> None:
    repo_path = _create_git_repo(tmp_path)
    (repo_path / "tracked.txt").write_text("after\n", encoding="utf-8")
    (repo_path / "z-new.txt").write_text("z\n", encoding="utf-8")
    nested_path = repo_path / "nested"
    nested_path.mkdir()
    (nested_path / "a-new.txt").write_text("a\n", encoding="utf-8")

    status = GitAnalyzer().status(repo_path)

    assert status.repo_root == repo_path.resolve()
    assert status.branch
    assert status.changed_paths == ("tracked.txt",)
    assert status.untracked_paths == ("nested/a-new.txt", "z-new.txt")


def test_git_analyzer_normalizes_backslashes_in_status_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = _create_git_repo(tmp_path)
    analyzer = GitAnalyzer()
    original_run = analyzer._run_git

    def return_windows_paths(
        candidate: Path,
        *args: str,
    ) -> subprocess.CompletedProcess[str]:
        if args[:2] == ("status", "--porcelain=v1"):
            return subprocess.CompletedProcess(
                ["git", *args],
                0,
                stdout=" M nested\\tracked.txt\n?? nested\\new.txt\n",
                stderr="",
            )
        return original_run(candidate, *args)

    monkeypatch.setattr(analyzer, "_run_git", return_windows_paths)

    status = analyzer.status(repo_path)

    assert status.changed_paths == ("nested/tracked.txt",)
    assert status.untracked_paths == ("nested/new.txt",)


def test_git_analyzer_preserves_arrow_inside_quoted_rename_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = _create_git_repo(tmp_path)
    analyzer = GitAnalyzer()
    original_run = analyzer._run_git

    def return_quoted_rename(
        candidate: Path,
        *args: str,
    ) -> subprocess.CompletedProcess[str]:
        if args[:2] == ("status", "--porcelain=v1"):
            return subprocess.CompletedProcess(
                ["git", *args],
                0,
                stdout='R  "old -> literal.txt" -> "new -> literal.txt"\n',
                stderr="",
            )
        return original_run(candidate, *args)

    monkeypatch.setattr(analyzer, "_run_git", return_quoted_rename)

    status = analyzer.status(repo_path)

    assert status.changed_paths == ("new -> literal.txt",)


def test_git_analyzer_preserves_literal_backslash_in_quoted_status_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = _create_git_repo(tmp_path)
    analyzer = GitAnalyzer()
    original_run = analyzer._run_git

    def return_quoted_backslash(
        candidate: Path,
        *args: str,
    ) -> subprocess.CompletedProcess[str]:
        if args[:2] == ("status", "--porcelain=v1"):
            return subprocess.CompletedProcess(
                ["git", *args],
                0,
                stdout=' M "folder\\\\name.txt"\n',
                stderr="",
            )
        return original_run(candidate, *args)

    monkeypatch.setattr(analyzer, "_run_git", return_quoted_backslash)

    status = analyzer.status(repo_path)

    assert status.changed_paths == (r"folder\name.txt",)


def test_git_analyzer_parses_worktree_diff_with_diff_parser(tmp_path: Path) -> None:
    repo_path = _create_git_repo(tmp_path)
    (repo_path / "tracked.txt").write_text("after\nextra\n", encoding="utf-8")

    summary = GitAnalyzer().diff(repo_path)

    assert summary.additions == 2
    assert summary.deletions == 1
    assert summary.files[0].path == "tracked.txt"
    assert summary.files[0].change_kind is ChangeKind.MODIFIED


def test_git_analyzer_rejects_missing_repository_directory(tmp_path: Path) -> None:
    with pytest.raises(GitAnalysisError, match="repository path must be an existing directory"):
        GitAnalyzer().status(tmp_path / "missing")


def test_git_analyzer_rejects_non_git_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def return_non_git_failure(
        *args: object,
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            ["git", "rev-parse", "--show-toplevel"],
            128,
            stdout="",
            stderr="fatal: not a git repository\n",
        )

    monkeypatch.setattr(git_module.subprocess, "run", return_non_git_failure)

    with pytest.raises(GitAnalysisError, match="not a git repository"):
        GitAnalyzer().status(tmp_path)


def test_git_analyzer_wraps_unavailable_git_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_to_start(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("git executable is missing")

    monkeypatch.setattr(git_module.subprocess, "run", fail_to_start)

    with pytest.raises(GitAnalysisError, match="git executable is unavailable"):
        GitAnalyzer().status(tmp_path)


def test_git_analyzer_wraps_git_startup_os_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_to_start(*args: object, **kwargs: object) -> None:
        raise PermissionError("git executable cannot be started")

    monkeypatch.setattr(git_module.subprocess, "run", fail_to_start)

    with pytest.raises(GitAnalysisError, match="git executable is unavailable"):
        GitAnalyzer().status(tmp_path)


def test_git_analyzer_wraps_failed_git_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def return_failure(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            ["git", "rev-parse", "--show-toplevel"],
            128,
            stdout="",
            stderr="fatal: synthetic failure\n",
        )

    monkeypatch.setattr(git_module.subprocess, "run", return_failure)

    with pytest.raises(GitAnalysisError, match="fatal: synthetic failure"):
        GitAnalyzer().status(tmp_path)


def test_git_analyzer_uses_only_allowed_read_only_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def return_git_result(
        args: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        command = tuple(args[1:])
        if command == ("rev-parse", "--show-toplevel"):
            stdout = str(tmp_path)
        elif command == ("branch", "--show-current"):
            stdout = "main\n"
        elif command == ("status", "--porcelain=v1", "--untracked-files=all"):
            stdout = ""
        elif command == ("diff", "--find-renames", "--no-ext-diff", "--unified=0", "HEAD"):
            stdout = ""
        else:
            raise AssertionError(f"unexpected git command: {command}")
        return subprocess.CompletedProcess(args, returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(git_module.subprocess, "run", return_git_result)

    analyzer = GitAnalyzer()
    analyzer.status(tmp_path)
    analyzer.diff(tmp_path)

    assert [tuple(args[1:]) for args, _ in calls] == [
        ("rev-parse", "--show-toplevel"),
        ("branch", "--show-current"),
        ("status", "--porcelain=v1", "--untracked-files=all"),
        ("rev-parse", "--show-toplevel"),
        ("diff", "--find-renames", "--no-ext-diff", "--unified=0", "HEAD"),
    ]
    for _, kwargs in calls:
        assert kwargs == {
            "cwd": tmp_path,
            "check": False,
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "shell": False,
        }
