"""编排会话评测：声明对账、意图裁决、确定性评分与 trace。

run_eval 是 Phase 4 的第一条 eval 流水线：取最新一条任务报告（agent 声明），
采集相对指定 base 的 git diff（真相），用确定性的 ``reconcile_scope`` 找出文件集合
层的差值，再把"差值是否在任务意图之内"交给可注入的 IntentJudge。默认判官给出
确定性的 needs_review，不触达任何 LLM/网络；真正的 LLM 判官后续按同一接口注入。

编排沿用与 ``run_scan`` 相同的 WorkflowRunner：步骤顺序固定、每步状态写入 trace、
失败时保留可解释的部分结果并写出 ``agentops-trace.json``。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from agentops.analyzers.git import GitAnalyzer
from agentops.core.artifact import Artifact
from agentops.core.eval import EvalResult, IntentVerdict
from agentops.core.evidence import DiffSummary
from agentops.core.session import SessionTrace, TaskReport
from agentops.core.workflow import WorkflowStatus, WorkflowTrace
from agentops.evaluators.scope_drift import ScopeDriftReport, reconcile_scope
from agentops.evaluators.session_eval import evaluate_scope
from agentops.judges import DeterministicIntentJudge, IntentJudge
from agentops.parsers.transcript import TranscriptParser
from agentops.runtime.workflow import WorkflowRunner, WorkflowStep
from agentops.writers.eval_report import EvalReportWriter
from agentops.writers.trace import TraceWriter


@dataclass(frozen=True)
class EvalRunResult:
    """聚合一次会话评测的结构化结果和产物。"""

    result: EvalResult
    artifacts: tuple[Artifact, ...]
    trace: WorkflowTrace


class EvalWorkflowError(RuntimeError):
    """暴露会话评测失败时保留下来的 workflow trace。"""

    def __init__(
        self,
        *,
        trace: WorkflowTrace,
        trace_artifact: Artifact | None,
    ) -> None:
        failed_step = trace.failures[0].step_name if trace.failures else "unknown"
        super().__init__(f"eval workflow failed at step: {failed_step}")
        self.trace = trace
        self.trace_artifact = trace_artifact


def run_eval(
    repo_path: Path,
    session_path: Path,
    output_dir: Path,
    *,
    diff_base: str = "HEAD",
    intent_judge: IntentJudge | None = None,
    timestamp: datetime | None = None,
) -> EvalRunResult:
    """评估最新一条任务报告，返回带分数、发现和意图裁决的 EvalResult。"""

    parser = TranscriptParser()
    analyzer = GitAnalyzer()
    report_writer = EvalReportWriter()
    # 默认走确定性判官：不接受任何 LLM/网络依赖，需复核交给后续 LLM 判官。
    judge = intent_judge or DeterministicIntentJudge()
    # 历史行的时间戳可注入（便于测试稳定）；默认取当前 UTC 时间。
    eval_timestamp = timestamp if timestamp is not None else datetime.now(timezone.utc)

    def parse_session(context: dict[str, object]) -> SessionTrace:
        return parser.parse(session_path)

    def select_task(context: dict[str, object]) -> TaskReport:
        session = cast(SessionTrace, context["session"])
        if not session.tasks:
            raise ValueError("session log has no task reports to evaluate")
        # 评估最新一条任务报告。
        return session.tasks[-1]

    def collect_diff(context: dict[str, object]) -> DiffSummary:
        return analyzer.diff(repo_path, base=diff_base)

    def reconcile(context: dict[str, object]) -> ScopeDriftReport:
        return reconcile_scope(
            cast(TaskReport, context["task"]),
            cast(DiffSummary, context["diff"]),
        )

    def judge_intent(context: dict[str, object]) -> tuple[IntentVerdict, ...]:
        return judge.judge(
            cast(TaskReport, context["task"]),
            cast(ScopeDriftReport, context["scope"]),
        )

    def build_eval_result(context: dict[str, object]) -> EvalResult:
        task = cast(TaskReport, context["task"])
        scope = cast(ScopeDriftReport, context["scope"])
        verdicts = cast("tuple[IntentVerdict, ...]", context["verdicts"])
        scope_eval = evaluate_scope(scope)
        return EvalResult(
            repo_root=Path(repo_path),
            task_title=task.title,
            declared_paths=scope.declared_paths,
            changed_paths=scope.changed_paths,
            score=scope_eval.score,
            findings=scope_eval.findings,
            recommendations=scope_eval.recommendations,
            intent_verdicts=verdicts,
        )

    def write_eval_artifacts(context: dict[str, object]) -> tuple[Artifact, ...]:
        return report_writer.write(
            cast(EvalResult, context["result"]),
            output_dir,
            timestamp=eval_timestamp,
        )

    # 编排层只维护步骤顺序；解析、采集、对账、裁决、评分和写出细节留在各自模块。
    execution = WorkflowRunner().run(
        workflow_name="session_eval",
        steps=(
            WorkflowStep(
                name="parse_session",
                action=parse_session,
                result_key="session",
            ),
            WorkflowStep(
                name="select_task",
                action=select_task,
                result_key="task",
            ),
            WorkflowStep(
                name="collect_diff",
                action=collect_diff,
                result_key="diff",
            ),
            WorkflowStep(
                name="reconcile_scope",
                action=reconcile,
                result_key="scope",
            ),
            WorkflowStep(
                name="judge_intent",
                action=judge_intent,
                result_key="verdicts",
            ),
            WorkflowStep(
                name="build_eval_result",
                action=build_eval_result,
                result_key="result",
            ),
            WorkflowStep(
                name="write_eval_artifacts",
                action=write_eval_artifacts,
                result_key="artifacts",
            ),
        ),
    )

    try:
        trace_artifact = TraceWriter().write(execution.trace, output_dir)
    except Exception:
        if execution.trace.status is WorkflowStatus.FAILED:
            raise EvalWorkflowError(
                trace=execution.trace,
                trace_artifact=None,
            ) from None
        raise

    if execution.trace.status is WorkflowStatus.FAILED:
        raise EvalWorkflowError(
            trace=execution.trace,
            trace_artifact=trace_artifact,
        )

    return EvalRunResult(
        result=cast(EvalResult, execution.context["result"]),
        artifacts=(
            *cast("tuple[Artifact, ...]", execution.context["artifacts"]),
            trace_artifact,
        ),
        trace=execution.trace,
    )
