from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from agentops.core import ArtifactKind, IntentVerdict
from agentops.core.eval import (
    SOURCE_DETERMINISTIC,
    SOURCE_LLM,
    VERDICT_DRIFT,
    VERDICT_NEEDS_REVIEW,
)
from agentops.core.session import TaskReport
from agentops.core.workflow import WorkflowEventType, WorkflowStatus
from agentops.evaluators.scope_drift import ScopeDriftReport
from agentops.judges.llm_intent import LLMIntentJudge
from agentops.llm.client import LLMError, LLMRequest, LLMResponse
from agentops.runtime.eval import EvalWorkflowError, run_eval
from agentops.writers.trace import TraceWriter


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
    """创建含一个基线提交（src/auth.py）的临时 Git 仓库。"""

    repo_path = tmp_path / "repo"
    (repo_path / "src").mkdir(parents=True)
    _run_git(repo_path, "init")
    _run_git(repo_path, "config", "user.email", "agentops@example.com")
    _run_git(repo_path, "config", "user.name", "AgentOps Test")
    (repo_path / "src" / "auth.py").write_text("before\n", encoding="utf-8")
    _run_git(repo_path, "add", "src/auth.py")
    _run_git(repo_path, "commit", "-m", "baseline")
    return repo_path


def _task(title: str, *changed_files: str) -> str:
    """构造一个带 Changed Files 声明的最小任务报告块。"""

    declared = "\n".join(f"- `{path}`" for path in changed_files) or "- (none)"
    return (
        f"## Task: {title}\n\n"
        "### Goal\n"
        "Do the thing.\n\n"
        "### Changes\n"
        "- Implemented the thing.\n\n"
        "### Changed Files\n"
        f"{declared}\n\n"
        "### Verification\n"
        "- Command: `python -m pytest`\n"
        "- Result: `ok`\n"
    )


def _write_session(repo_path: Path, *task_blocks: str) -> Path:
    """把任务块写入仓库内默认的会话日志路径。"""

    session_path = repo_path / ".agentops" / "agentops-session.md"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text("\n".join(task_blocks), encoding="utf-8")
    return session_path


def _stage_undeclared_change(repo_path: Path) -> None:
    """修改已声明文件，并新增一个未声明但出现在 diff 真相里的文件。"""

    (repo_path / "src" / "auth.py").write_text("after\n", encoding="utf-8")
    (repo_path / "src" / "billing.py").write_text("new\n", encoding="utf-8")
    # 新文件必须入暂存区，git diff HEAD 才会把它当作真相的一部分。
    _run_git(repo_path, "add", "src/billing.py")


def _worktree_snapshot(root: Path) -> tuple[tuple[str, bytes], ...]:
    """对工作区文件做快照，跳过 .git 内部状态（只读 git 命令会刷新索引）。"""

    return tuple(
        sorted(
            (path.relative_to(root).as_posix(), path.read_bytes())
            for path in root.rglob("*")
            if path.is_file() and ".git" not in path.relative_to(root).parts
        )
    )


class _StubJudge:
    """记录调用并返回预置裁决的可注入意图判官。"""

    def __init__(self, verdicts: tuple[IntentVerdict, ...]) -> None:
        self._verdicts = verdicts
        self.calls: list[tuple[TaskReport, ScopeDriftReport]] = []

    def judge(
        self, task_report: TaskReport, report: ScopeDriftReport
    ) -> tuple[IntentVerdict, ...]:
        self.calls.append((task_report, report))
        return self._verdicts


class _StubLLMClient:
    """记录请求并回放预置文本（或抛错）的 LLMClient 替身；绝不触网。"""

    def __init__(self, *, text: str | None = None, error: Exception | None = None) -> None:
        self._text = text
        self._error = error
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        assert self._text is not None
        return LLMResponse(text=self._text)


def test_run_eval_orchestrates_session_eval_workflow(tmp_path: Path) -> None:
    repo_path = _create_git_repo(tmp_path)
    _stage_undeclared_change(repo_path)
    session_path = _write_session(repo_path, _task("Fix login", "src/auth.py"))
    output_dir = tmp_path / "output"

    run = run_eval(repo_path, session_path, output_dir)

    result = run.result
    assert result.task_title == "Fix login"
    assert result.declared_paths == ("src/auth.py",)
    assert result.changed_paths == ("src/auth.py", "src/billing.py")
    # 未声明改动扣 15 分，且必须带文件证据与可执行建议。
    assert result.score == 85
    assert [finding.code for finding in result.findings] == ["undeclared_change"]
    assert result.findings[0].evidence == ("src/billing.py",)
    assert result.recommendations
    # 默认判官把意图判断标为需复核，来源是确定性。
    assert len(result.intent_verdicts) == 1
    assert result.intent_verdicts[0].verdict == VERDICT_NEEDS_REVIEW
    assert result.intent_verdicts[0].source == SOURCE_DETERMINISTIC

    assert run.trace.status is WorkflowStatus.COMPLETED
    assert [
        event.step_name
        for event in run.trace.events
        if event.event_type is WorkflowEventType.STEP_COMPLETED
    ] == [
        "parse_session",
        "select_task",
        "collect_diff",
        "reconcile_scope",
        "judge_intent",
        "build_eval_result",
        "write_eval_artifacts",
    ]
    assert {artifact.kind for artifact in run.artifacts} == {
        ArtifactKind.MARKDOWN_REPORT,
        ArtifactKind.JSON_SCORE,
        ArtifactKind.EVAL_HISTORY,
        ArtifactKind.WORKFLOW_TRACE,
    }
    assert (output_dir / "agentops-report.md").exists()
    assert (output_dir / "agentops-score.json").exists()
    assert (output_dir / "eval-history.jsonl").exists()
    trace_path = output_dir / "agentops-trace.json"
    assert json.loads(trace_path.read_text(encoding="utf-8"))["status"] == "completed"


def test_run_eval_evaluates_most_recent_task(tmp_path: Path) -> None:
    repo_path = _create_git_repo(tmp_path)
    _stage_undeclared_change(repo_path)
    # 最新任务正确声明了两处真相改动，应得满分、无 findings。
    session_path = _write_session(
        repo_path,
        _task("Old task", "src/legacy.py"),
        _task("Latest task", "src/auth.py", "src/billing.py"),
    )

    run = run_eval(repo_path, session_path, tmp_path / "output")

    assert run.result.task_title == "Latest task"
    assert run.result.score == 100
    assert run.result.findings == ()
    assert run.result.intent_verdicts == ()


def test_run_eval_uses_injected_intent_judge(tmp_path: Path) -> None:
    repo_path = _create_git_repo(tmp_path)
    _stage_undeclared_change(repo_path)
    session_path = _write_session(repo_path, _task("Fix login", "src/auth.py"))
    stub_verdict = IntentVerdict(
        finding_code="intent_alignment",
        evidence=("model says drift",),
        verdict=VERDICT_DRIFT,
        rationale="the billing change is outside the login task",
        source=SOURCE_LLM,
    )
    judge = _StubJudge((stub_verdict,))

    run = run_eval(repo_path, session_path, tmp_path / "output", intent_judge=judge)

    assert judge.calls, "injected judge should be consulted"
    assert run.result.intent_verdicts == (stub_verdict,)


def test_run_eval_keeps_target_repository_read_only(tmp_path: Path) -> None:
    repo_path = _create_git_repo(tmp_path)
    _stage_undeclared_change(repo_path)
    session_path = _write_session(repo_path, _task("Fix login", "src/auth.py"))
    before = _worktree_snapshot(repo_path)

    run_eval(repo_path, session_path, tmp_path / "output")

    assert _worktree_snapshot(repo_path) == before


def test_run_eval_honors_configurable_diff_base(tmp_path: Path) -> None:
    repo_path = _create_git_repo(tmp_path)
    # 第二次提交把 auth.py 改掉，并新增 billing.py。
    (repo_path / "src" / "auth.py").write_text("after\n", encoding="utf-8")
    (repo_path / "src" / "billing.py").write_text("new\n", encoding="utf-8")
    _run_git(repo_path, "add", "src/auth.py", "src/billing.py")
    _run_git(repo_path, "commit", "-m", "second")
    session_path = _write_session(repo_path, _task("Fix login", "src/auth.py"))

    # 相对 HEAD 工作区干净：diff 真相为空。
    head_run = run_eval(repo_path, session_path, tmp_path / "head")
    assert head_run.result.changed_paths == ()

    # 相对第一次提交：两处改动进入真相，billing.py 成为未声明改动（扣 15 分）。
    base_run = run_eval(
        repo_path, session_path, tmp_path / "base", diff_base="HEAD~1"
    )
    assert base_run.result.changed_paths == ("src/auth.py", "src/billing.py")
    assert base_run.result.score == 85


def test_run_eval_fails_with_structured_error_for_missing_session(
    tmp_path: Path,
) -> None:
    repo_path = _create_git_repo(tmp_path)
    output_dir = tmp_path / "output"

    with pytest.raises(EvalWorkflowError) as exc_info:
        run_eval(repo_path, repo_path / ".agentops" / "missing.md", output_dir)

    error = exc_info.value
    assert error.trace.status is WorkflowStatus.FAILED
    assert error.trace.failures[0].step_name == "parse_session"
    assert error.trace_artifact is not None
    assert json.loads(
        error.trace_artifact.path.read_text(encoding="utf-8")
    )["status"] == "failed"


def test_run_eval_fails_with_structured_error_for_empty_log(tmp_path: Path) -> None:
    repo_path = _create_git_repo(tmp_path)
    session_path = _write_session(repo_path, "")

    with pytest.raises(EvalWorkflowError) as exc_info:
        run_eval(repo_path, session_path, tmp_path / "output")

    assert exc_info.value.trace.failures[0].step_name == "select_task"


def test_run_eval_preserves_trace_after_diff_failure(tmp_path: Path) -> None:
    # 有效会话但仓库不是 git：解析与选取任务成功，采集 diff 这一步失败。
    non_git = tmp_path / "plain"
    session_path = _write_session(non_git, _task("Fix login", "src/auth.py"))

    with pytest.raises(EvalWorkflowError) as exc_info:
        run_eval(non_git, session_path, tmp_path / "output")

    assert exc_info.value.trace.failures[0].step_name == "collect_diff"


def test_run_eval_keeps_original_failure_when_trace_cannot_be_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_path = _create_git_repo(tmp_path)

    def fail_trace_write(
        writer: TraceWriter, trace: object, output_dir: Path
    ) -> object:
        raise OSError("trace write failed")

    monkeypatch.setattr(TraceWriter, "write", fail_trace_write)

    # workflow 成功但 trace 写出失败时，原始异常不应被吞掉。
    with pytest.raises(OSError, match="trace write failed"):
        run_eval(
            repo_path,
            _write_session(repo_path, _task("Fix login", "src/auth.py")),
            tmp_path / "output",
        )


def test_run_eval_flows_llm_intent_verdicts_into_result(tmp_path: Path) -> None:
    repo_path = _create_git_repo(tmp_path)
    _stage_undeclared_change(repo_path)
    session_path = _write_session(repo_path, _task("Fix login", "src/auth.py"))
    client = _StubLLMClient(
        text=json.dumps(
            [
                {
                    "finding_code": "undeclared_change",
                    "evidence": ["src/billing.py"],
                    "verdict": VERDICT_DRIFT,
                    "rationale": "billing is unrelated to the login task",
                }
            ]
        )
    )

    run = run_eval(
        repo_path, session_path, tmp_path / "output", intent_judge=LLMIntentJudge(client)
    )

    # 确定性分数不受意图裁决影响（仍是未声明改动扣 15）。
    assert run.result.score == 85
    assert client.requests, "the LLM judge should consult the injected client"
    assert len(run.result.intent_verdicts) == 1
    verdict = run.result.intent_verdicts[0]
    assert verdict.source == SOURCE_LLM
    assert verdict.verdict == VERDICT_DRIFT
    assert verdict.finding_code == "undeclared_change"
    assert verdict.evidence == ("src/billing.py",)
    # 工作流步骤形状不变。
    assert [
        event.step_name
        for event in run.trace.events
        if event.event_type is WorkflowEventType.STEP_COMPLETED
    ] == [
        "parse_session",
        "select_task",
        "collect_diff",
        "reconcile_scope",
        "judge_intent",
        "build_eval_result",
        "write_eval_artifacts",
    ]


def test_run_eval_degrading_llm_judge_matches_default_path(tmp_path: Path) -> None:
    repo_path = _create_git_repo(tmp_path)
    _stage_undeclared_change(repo_path)
    session_path = _write_session(repo_path, _task("Fix login", "src/auth.py"))

    # 默认（确定性）路径作为基准。
    default_run = run_eval(repo_path, session_path, tmp_path / "default")

    # 注入一个必然失败的 LLM 客户端：判官应降级到确定性，且结果与默认路径一致。
    degraded = run_eval(
        repo_path,
        session_path,
        tmp_path / "degraded",
        intent_judge=LLMIntentJudge(_StubLLMClient(error=LLMError("network down"))),
    )

    assert degraded.trace.status is WorkflowStatus.COMPLETED
    # 裁决不移动分数：降级运行与默认运行同分。
    assert degraded.result.score == default_run.result.score == 85
    # 降级裁决与默认确定性裁决逐字一致。
    assert degraded.result.intent_verdicts == default_run.result.intent_verdicts
    assert degraded.result.intent_verdicts
    assert all(
        verdict.source == SOURCE_DETERMINISTIC
        for verdict in degraded.result.intent_verdicts
    )
