from io import StringIO
from pathlib import Path
import json
import subprocess
from types import SimpleNamespace

import pytest

import agentops.cli as cli_module
from agentops.cli import build_parser, main, resolve_session_log_policy
from agentops.initializers import SessionLogPolicy
from agentops.llm.client import LLMError, LLMResponse


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


_EVAL_SESSION = """## Task: Fix login

### Goal
g

### Changes
- c

### Changed Files
- `src/auth.py`

### Verification
- Command: `run`
- Result: `ok`
"""


def _eval_git(repo_path: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        shell=False,
    )


def _eval_repo(tmp_path: Path) -> Path:
    """创建一个含基线提交、并带一处已声明工作区改动的 git 仓库。"""

    repo_path = tmp_path / "repo"
    (repo_path / "src").mkdir(parents=True)
    _eval_git(repo_path, "init")
    _eval_git(repo_path, "config", "user.email", "agentops@example.com")
    _eval_git(repo_path, "config", "user.name", "AgentOps Test")
    (repo_path / "src" / "auth.py").write_text("before\n", encoding="utf-8")
    _eval_git(repo_path, "add", "src/auth.py")
    _eval_git(repo_path, "commit", "-m", "baseline")
    # 工作区改动（已在会话日志里声明），相对 HEAD 即为真相。
    (repo_path / "src" / "auth.py").write_text("after\n", encoding="utf-8")
    return repo_path


def test_eval_command_writes_artifacts_and_prints_score(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_path = _eval_repo(tmp_path)
    # 默认会话路径：<repo>/.agentops/agentops-session.md。
    session = repo_path / ".agentops" / "agentops-session.md"
    session.parent.mkdir(parents=True, exist_ok=True)
    session.write_text(_EVAL_SESSION, encoding="utf-8")
    output_dir = tmp_path / "out"

    exit_code = main(["eval", "--repo", str(repo_path), "--output", str(output_dir)])

    assert exit_code == 0
    assert (output_dir / "agentops-report.md").exists()
    assert (output_dir / "agentops-score.json").exists()
    assert (output_dir / "agentops-trace.json").exists()
    assert (output_dir / "eval-history.jsonl").exists()
    output = capsys.readouterr().out
    # 声明与真相一致：满分。
    assert "AgentOps scope-discipline score: 100/100" in output
    assert "Wrote" in output


def test_eval_command_honors_custom_session_and_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_path = _eval_repo(tmp_path)
    session = tmp_path / "custom-session.md"
    session.write_text(_EVAL_SESSION, encoding="utf-8")
    output_dir = tmp_path / "custom-out"

    exit_code = main(
        [
            "eval",
            "--repo",
            str(repo_path),
            "--session",
            str(session),
            "--output",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "agentops-score.json").exists()


def test_eval_command_forwards_diff_base_to_run_eval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    captured: dict[str, object] = {}

    def capture_run_eval(
        repo_path: Path,
        session_path: Path,
        output_dir: Path,
        *,
        diff_base: str = "HEAD",
        **kwargs: object,
    ) -> object:
        captured.update(
            repo=repo_path,
            session=session_path,
            output=output_dir,
            diff_base=diff_base,
        )
        return SimpleNamespace(result=SimpleNamespace(score=100), artifacts=())

    monkeypatch.setattr(cli_module, "run_eval", capture_run_eval)

    exit_code = main(
        [
            "eval",
            "--repo",
            str(tmp_path / "repo"),
            "--diff-base",
            "HEAD~1",
            "--output",
            str(tmp_path / "out"),
        ]
    )

    assert exit_code == 0
    assert captured["diff_base"] == "HEAD~1"
    # 未显式提供 --session 时回退到 <repo>/.agentops/agentops-session.md。
    assert captured["session"] == tmp_path / "repo" / ".agentops" / "agentops-session.md"


def test_eval_command_reports_structured_workflow_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "out"

    # 仓库缺失时其默认会话也缺失，解析步骤失败，应是结构化错误而非 traceback。
    exit_code = main(
        ["eval", "--repo", str(tmp_path / "missing"), "--output", str(output_dir)]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "AgentOps eval failed at step: parse_session" in captured.err
    assert "Traceback" not in captured.err
    assert (output_dir / "agentops-trace.json").exists()


def test_eval_command_does_not_hide_unexpected_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_unexpectedly(*args: object, **kwargs: object) -> None:
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(cli_module, "run_eval", fail_unexpectedly)

    with pytest.raises(RuntimeError, match="unexpected failure"):
        main(["eval", "--repo", str(tmp_path), "--output", str(tmp_path / "out")])


def _eval_repo_with_undeclared(tmp_path: Path) -> Path:
    """在 _eval_repo 基础上新增一个未声明、已暂存的 src/billing.py。"""

    repo_path = _eval_repo(tmp_path)
    (repo_path / "src" / "billing.py").write_text("new\n", encoding="utf-8")
    _eval_git(repo_path, "add", "src/billing.py")
    return repo_path


def _write_default_session(repo_path: Path) -> None:
    session = repo_path / ".agentops" / "agentops-session.md"
    session.parent.mkdir(parents=True, exist_ok=True)
    session.write_text(_EVAL_SESSION, encoding="utf-8")


class _StubLLMClient:
    """回放固定 drift 裁决的 LLMClient 替身，供 CLI 测试注入（不触网）。"""

    def complete(self, request: object) -> LLMResponse:
        return LLMResponse(
            text=json.dumps(
                [
                    {
                        "finding_code": "undeclared_change",
                        "evidence": ["src/billing.py"],
                        "verdict": "drift",
                        "rationale": "billing is unrelated",
                    }
                ]
            )
        )


def test_eval_command_uses_llm_intent_judge_via_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_path = _eval_repo_with_undeclared(tmp_path)
    _write_default_session(repo_path)
    output_dir = tmp_path / "out"
    # monkeypatch 工厂注入 stub 客户端：CLI 测试绝不触网。
    monkeypatch.setattr(cli_module, "_build_llm_client", lambda args: _StubLLMClient())

    exit_code = main(
        [
            "eval",
            "--repo",
            str(repo_path),
            "--output",
            str(output_dir),
            "--intent-judge",
            "llm",
            "--intent-model",
            "mimo-v2.5-pro",
        ]
    )

    assert exit_code == 0
    score_data = json.loads(
        (output_dir / "agentops-score.json").read_text(encoding="utf-8")
    )
    verdicts = score_data["intent_verdicts"]
    assert any(verdict["source"] == "llm" for verdict in verdicts)
    assert any(verdict["verdict"] == "drift" for verdict in verdicts)
    # 裁决不移动分数：未声明改动仍扣 15。
    assert score_data["score"] == 85


def test_eval_command_default_uses_deterministic_judge(tmp_path: Path) -> None:
    repo_path = _eval_repo_with_undeclared(tmp_path)
    _write_default_session(repo_path)
    output_dir = tmp_path / "out"

    exit_code = main(["eval", "--repo", str(repo_path), "--output", str(output_dir)])

    assert exit_code == 0
    score_data = json.loads(
        (output_dir / "agentops-score.json").read_text(encoding="utf-8")
    )
    verdicts = score_data["intent_verdicts"]
    assert verdicts
    assert all(verdict["source"] == "deterministic" for verdict in verdicts)


def test_eval_command_llm_without_model_falls_back(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_path = _eval_repo_with_undeclared(tmp_path)
    _write_default_session(repo_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "eval",
            "--repo",
            str(repo_path),
            "--output",
            str(output_dir),
            "--intent-judge",
            "llm",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "fell back to deterministic" in captured.err
    assert "no --intent-model" in captured.err
    # 仍然产出确定性裁决。
    score_data = json.loads(
        (output_dir / "agentops-score.json").read_text(encoding="utf-8")
    )
    assert all(v["source"] == "deterministic" for v in score_data["intent_verdicts"])


def test_eval_command_llm_unconstructable_client_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_path = _eval_repo_with_undeclared(tmp_path)
    _write_default_session(repo_path)

    def boom(args: object) -> object:
        raise LLMError("missing API key")

    monkeypatch.setattr(cli_module, "_build_llm_client", boom)

    exit_code = main(
        [
            "eval",
            "--repo",
            str(repo_path),
            "--output",
            str(tmp_path / "out"),
            "--intent-judge",
            "llm",
            "--intent-model",
            "mimo-v2.5-pro",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "fell back to deterministic" in captured.err
    assert "missing API key" in captured.err


def test_eval_command_rejects_unknown_intent_judge(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "eval",
                "--repo",
                str(tmp_path / "repo"),
                "--intent-judge",
                "bogus",
            ]
        )

    assert exc_info.value.code == 2


_MEMORY_HISTORY_LINE = json.dumps(
    {
        "timestamp": "2026-06-06T00:00:00+00:00",
        "result": {
            "score": 80,
            "findings": [
                {
                    "code": "undeclared_change",
                    "severity": "warning",
                    "message": "m",
                    "evidence": ["src/a.py"],
                }
            ],
            "intent_verdicts": [],
        },
        "verdict_summary": {},
    },
    sort_keys=True,
)


def _write_history_file(path: Path, *lines: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_memory_command_writes_artifacts_and_prints_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_path = tmp_path / "repo"
    # 默认历史路径：<repo>/.agentops/eval-history.jsonl。
    _write_history_file(
        repo_path / ".agentops" / "eval-history.jsonl",
        _MEMORY_HISTORY_LINE,
        _MEMORY_HISTORY_LINE,
    )
    output_dir = tmp_path / "out"

    exit_code = main(["memory", "--repo", str(repo_path), "--output", str(output_dir)])

    assert exit_code == 0
    assert (output_dir / "agentops-memory.md").exists()
    assert (output_dir / "agentops-memory.json").exists()
    assert (output_dir / "skill-candidates.md").exists()
    assert (output_dir / "agentops-trace.json").exists()
    output = capsys.readouterr().out
    assert "AgentOps repository memory:" in output
    assert "Wrote" in output


def test_memory_command_honors_custom_history_and_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    history = tmp_path / "custom-history.jsonl"
    _write_history_file(history, _MEMORY_HISTORY_LINE)
    output_dir = tmp_path / "custom-out"

    exit_code = main(
        [
            "memory",
            "--repo",
            str(tmp_path / "repo"),
            "--history",
            str(history),
            "--output",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "agentops-memory.json").exists()


def test_memory_command_defaults_history_to_repo_agentops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def capture_run_memory(
        repo_path: Path,
        history_path: Path,
        output_dir: Path,
        **kwargs: object,
    ) -> object:
        captured.update(repo=repo_path, history=history_path, output=output_dir)
        return SimpleNamespace(
            memory=SimpleNamespace(
                sample_count=1,
                trend=SimpleNamespace(direction="unknown"),
                failure_modes=(),
                rule_candidates=(),
                skill_candidates=(),
            ),
            artifacts=(),
        )

    monkeypatch.setattr(cli_module, "run_memory", capture_run_memory)

    exit_code = main(
        ["memory", "--repo", str(tmp_path / "repo"), "--output", str(tmp_path / "out")]
    )

    assert exit_code == 0
    # 未显式提供 --history 时回退到 <repo>/.agentops/eval-history.jsonl。
    assert (
        captured["history"]
        == tmp_path / "repo" / ".agentops" / "eval-history.jsonl"
    )


def test_memory_command_reports_structured_failure_for_missing_history(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "out"

    # 历史缺失时给出结构化错误而非 traceback，并指引先跑 eval。
    exit_code = main(
        ["memory", "--repo", str(tmp_path / "missing"), "--output", str(output_dir)]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "run agentops eval first" in captured.err
    assert "Traceback" not in captured.err
    assert (output_dir / "agentops-trace.json").exists()


def test_memory_command_does_not_hide_unexpected_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_unexpectedly(*args: object, **kwargs: object) -> None:
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(cli_module, "run_memory", fail_unexpectedly)

    with pytest.raises(RuntimeError, match="unexpected failure"):
        main(["memory", "--repo", str(tmp_path), "--output", str(tmp_path / "out")])


_SUGGEST_HISTORY_LINE = json.dumps(
    {
        "timestamp": "2026-06-07T00:00:00+00:00",
        "result": {
            "score": 80,
            "findings": [
                {
                    "code": "undeclared_change",
                    "severity": "warning",
                    "message": "m",
                    "evidence": ["src/a.py"],
                }
            ],
            "intent_verdicts": [],
        },
        "verdict_summary": {},
    },
    sort_keys=True,
)


def test_suggest_command_writes_artifacts_and_prints_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_path = tmp_path / "repo"
    # 默认历史路径：<repo>/.agentops/eval-history.jsonl。
    _write_history_file(
        repo_path / ".agentops" / "eval-history.jsonl",
        _SUGGEST_HISTORY_LINE,
        _SUGGEST_HISTORY_LINE,
    )
    output_dir = tmp_path / "out"

    exit_code = main(
        ["suggest", "--repo", str(repo_path), "--output", str(output_dir)]
    )

    assert exit_code == 0
    assert (output_dir / "suggested-claude-md.md").exists()
    assert (output_dir / "suggested-agents-md.md").exists()
    assert (output_dir / "suggested-hooks.md").exists()
    assert (output_dir / "agentops-suggestions.json").exists()
    assert (output_dir / "agentops-trace.json").exists()
    output = capsys.readouterr().out
    assert "AgentOps repository suggestions:" in output
    assert "Wrote" in output


def test_suggest_command_honors_custom_history_and_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    history = tmp_path / "custom-history.jsonl"
    _write_history_file(history, _SUGGEST_HISTORY_LINE)
    output_dir = tmp_path / "custom-out"

    exit_code = main(
        [
            "suggest",
            "--repo",
            str(tmp_path / "repo"),
            "--history",
            str(history),
            "--output",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "agentops-suggestions.json").exists()


def test_suggest_command_defaults_history_to_repo_agentops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def capture_run_suggest(
        repo_path: Path,
        history_path: Path,
        output_dir: Path,
        **kwargs: object,
    ) -> object:
        captured.update(repo=repo_path, history=history_path, output=output_dir)
        return SimpleNamespace(
            assets=SimpleNamespace(
                sample_count=1,
                trend_summary="Scope-discipline trend is unknown over 1 eval(s).",
                instruction_suggestions=(),
                hook_proposals=(),
                skill_candidates=(),
            ),
            artifacts=(),
        )

    monkeypatch.setattr(cli_module, "run_suggest", capture_run_suggest)

    exit_code = main(
        ["suggest", "--repo", str(tmp_path / "repo"), "--output", str(tmp_path / "out")]
    )

    assert exit_code == 0
    # 未显式提供 --history 时回退到 <repo>/.agentops/eval-history.jsonl。
    assert (
        captured["history"] == tmp_path / "repo" / ".agentops" / "eval-history.jsonl"
    )


def test_suggest_command_reports_structured_failure_for_missing_history(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "out"

    # 历史缺失时给出结构化错误而非 traceback，并指引先跑 eval。
    exit_code = main(
        ["suggest", "--repo", str(tmp_path / "missing"), "--output", str(output_dir)]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "run agentops eval first" in captured.err
    assert "Traceback" not in captured.err
    assert (output_dir / "agentops-trace.json").exists()


def test_suggest_command_does_not_hide_unexpected_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_unexpectedly(*args: object, **kwargs: object) -> None:
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(cli_module, "run_suggest", fail_unexpectedly)

    with pytest.raises(RuntimeError, match="unexpected failure"):
        main(["suggest", "--repo", str(tmp_path), "--output", str(tmp_path / "out")])

