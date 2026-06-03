from io import StringIO
from pathlib import Path

import pytest

import agentops.cli as cli_module
from agentops.cli import build_parser, main, resolve_session_log_policy
from agentops.initializers import SessionLogPolicy


def test_cli_parser_has_program_description() -> None:
    parser = build_parser()

    assert parser.prog == "agentops"
    assert "AI coding" in parser.description


def test_cli_main_accepts_no_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage: agentops" in capsys.readouterr().out


def test_cli_version_prints_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == "0.1.0"


def test_cli_rejects_phase_one_scan_command() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["scan"])

    assert exc_info.value.code == 2


def test_scan_command_writes_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "README.md").write_text("# Demo", encoding="utf-8")
    output_dir = tmp_path / "output"

    exit_code = main(
        [
            "scan",
            "--repo",
            str(repo_path),
            "--output",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "agentops-report.md").exists()
    assert (output_dir / "agentops-score.json").exists()
    assert (output_dir / "agentops-trace.json").exists()
    output = capsys.readouterr().out
    assert "AgentOps readiness score:" in output
    assert "Wrote" in output


def test_scan_command_uses_default_output_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    monkeypatch.chdir(tmp_path)

    assert main(["scan", "--repo", str(repo_path)]) == 0
    assert (tmp_path / ".agentops" / "agentops-report.md").exists()
    assert (tmp_path / ".agentops" / "agentops-score.json").exists()
    assert (tmp_path / ".agentops" / "agentops-trace.json").exists()


def test_scan_command_reports_structured_workflow_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "output"

    exit_code = main(
        [
            "scan",
            "--repo",
            str(tmp_path / "missing"),
            "--output",
            str(output_dir),
        ]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "AgentOps scan failed at step: scan_repository\n"
        f"Wrote {output_dir / 'agentops-trace.json'}\n"
    )
    assert (output_dir / "agentops-trace.json").exists()


def test_scan_command_does_not_hide_unexpected_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_unexpectedly(repo_path: Path, output_dir: Path) -> None:
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(cli_module, "run_scan", fail_unexpectedly)

    with pytest.raises(RuntimeError, match="unexpected failure"):
        main(["scan", "--repo", str(tmp_path)])


@pytest.mark.parametrize(
    "policy",
    [
        SessionLogPolicy.PRIVATE,
        SessionLogPolicy.TRACKED,
        SessionLogPolicy.UNMANAGED,
    ],
)
def test_init_command_accepts_explicit_session_log_policy(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    policy: SessionLogPolicy,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    exit_code = main(
        [
            "init",
            "--repo",
            str(repo_path),
            "--session-log-policy",
            policy.value,
        ]
    )

    assert exit_code == 0
    assert (repo_path / ".agentops" / "session-protocol.md").exists()
    assert (repo_path / ".agentops" / "agentops-session.md").exists()
    output = capsys.readouterr().out
    assert f"Wrote {repo_path / '.agentops' / 'session-protocol.md'}" in output
    assert f"Wrote {repo_path / '.agentops' / 'agentops-session.md'}" in output


def test_init_command_defaults_to_private_policy_for_non_interactive_stdin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    monkeypatch.setattr(cli_module.sys, "stdin", StringIO())

    assert main(["init", "--repo", str(repo_path)]) == 0
    assert "agentops-session.md" in (
        repo_path / ".agentops" / ".gitignore"
    ).read_text(encoding="utf-8")


def test_resolve_session_log_policy_returns_explicit_policy_without_prompting() -> None:
    def fail_if_prompted(prompt: str) -> str:
        raise AssertionError(f"unexpected prompt: {prompt}")

    assert (
        resolve_session_log_policy(
            SessionLogPolicy.TRACKED,
            stdin_isatty=True,
            input_fn=fail_if_prompted,
        )
        is SessionLogPolicy.TRACKED
    )


def test_resolve_session_log_policy_defaults_to_private_without_tty() -> None:
    def fail_if_prompted(prompt: str) -> str:
        raise AssertionError(f"unexpected prompt: {prompt}")

    assert (
        resolve_session_log_policy(
            None,
            stdin_isatty=False,
            input_fn=fail_if_prompted,
        )
        is SessionLogPolicy.PRIVATE
    )


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("1", SessionLogPolicy.PRIVATE),
        ("2", SessionLogPolicy.TRACKED),
        ("3", SessionLogPolicy.UNMANAGED),
    ],
)
def test_resolve_session_log_policy_maps_interactive_choices(
    answer: str,
    expected: SessionLogPolicy,
) -> None:
    assert (
        resolve_session_log_policy(
            None,
            stdin_isatty=True,
            input_fn=lambda prompt: answer,
        )
        is expected
    )


def test_resolve_session_log_policy_reprompts_for_unsupported_answer() -> None:
    answers = iter(["unsupported", "2"])
    prompts: list[str] = []

    def answer(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    assert (
        resolve_session_log_policy(None, stdin_isatty=True, input_fn=answer)
        is SessionLogPolicy.TRACKED
    )
    assert len(prompts) == 2


def test_init_command_reports_structured_initialization_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing_repo = tmp_path / "missing"

    assert (
        main(
            [
                "init",
                "--repo",
                str(missing_repo),
                "--session-log-policy",
                "private",
            ]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "AgentOps initialization failed: "
        "repository path must be an existing directory\n"
    )
    assert "Traceback" not in captured.err


def test_init_command_does_not_hide_unexpected_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_unexpectedly(
        repo_path: Path,
        session_log_policy: SessionLogPolicy,
    ) -> None:
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(cli_module, "run_init", fail_unexpectedly)

    with pytest.raises(RuntimeError, match="unexpected failure"):
        main(
            [
                "init",
                "--repo",
                str(tmp_path),
                "--session-log-policy",
                "private",
            ]
        )


CHECK_TASK = """## Task: T

### Goal
g

### Changes
- c

### Verification
- Command: `run`
- Result: `ok`
"""


def test_check_session_log_returns_zero_after_new_append(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    log = repo_path / ".agentops" / "agentops-session.md"
    log.parent.mkdir(parents=True)
    log.write_text(CHECK_TASK, encoding="utf-8")

    # 首次检查会记录基线并提醒；追加新任务后应返回 0。
    main(["check-session-log", "--repo", str(repo_path)])
    log.write_text(
        CHECK_TASK + "\n" + CHECK_TASK.replace("## Task: T", "## Task: T2"),
        encoding="utf-8",
    )

    assert main(["check-session-log", "--repo", str(repo_path)]) == 0


def test_check_session_log_reminds_when_stale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_path = tmp_path / "repo"
    log = repo_path / ".agentops" / "agentops-session.md"
    log.parent.mkdir(parents=True)
    log.write_text(CHECK_TASK, encoding="utf-8")

    main(["check-session-log", "--repo", str(repo_path)])  # 记录基线
    capsys.readouterr()  # 清空首次输出

    exit_code = main(["check-session-log", "--repo", str(repo_path)])  # 内容未变

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "agentops-session.md" in captured.err
    assert "Traceback" not in captured.err


def test_check_session_log_reports_missing_repo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["check-session-log", "--repo", str(tmp_path / "missing")])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "does not exist" in captured.err
    assert "Traceback" not in captured.err
