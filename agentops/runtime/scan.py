"""编排仓库扫描、readiness 评估和产物写出。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from agentops.core.artifact import Artifact
from agentops.core.evaluation import ReadinessReport
from agentops.core.repo import RepoProfile
from agentops.core.workflow import WorkflowStatus, WorkflowTrace
from agentops.evaluators.readiness import ReadinessEvaluator
from agentops.runtime.workflow import WorkflowRunner, WorkflowStep
from agentops.scanners.repo import RepoScanner
from agentops.writers.report import ReportWriter
from agentops.writers.trace import TraceWriter


@dataclass(frozen=True)
class ScanResult:
    """聚合一次仓库 readiness 扫描的结构化结果和产物。"""

    report: ReadinessReport
    artifacts: tuple[Artifact, ...]
    trace: WorkflowTrace


class ScanWorkflowError(RuntimeError):
    """暴露仓库扫描失败时保留下来的 workflow trace。"""

    def __init__(
        self,
        *,
        trace: WorkflowTrace,
        trace_artifact: Artifact | None,
    ) -> None:
        failed_step = trace.failures[0].step_name if trace.failures else "unknown"
        super().__init__(f"scan workflow failed at step: {failed_step}")
        self.trace = trace
        self.trace_artifact = trace_artifact


def run_scan(repo_path: Path, output_dir: Path) -> ScanResult:
    """按照固定流水线执行仓库 readiness 扫描。"""

    scanner = RepoScanner()
    evaluator = ReadinessEvaluator()
    report_writer = ReportWriter()

    def scan_repository(context: dict[str, object]) -> RepoProfile:
        return scanner.scan(repo_path)

    def evaluate_readiness(context: dict[str, object]) -> ReadinessReport:
        return evaluator.evaluate(cast(RepoProfile, context["profile"]))

    def write_readiness_artifacts(
        context: dict[str, object],
    ) -> tuple[Artifact, ...]:
        return report_writer.write(cast(ReadinessReport, context["report"]), output_dir)

    # 编排层只维护步骤顺序，扫描、评估和写出细节分别留在独立模块。
    execution = WorkflowRunner().run(
        workflow_name="repo_scan",
        steps=(
            WorkflowStep(
                name="scan_repository",
                action=scan_repository,
                result_key="profile",
            ),
            WorkflowStep(
                name="evaluate_readiness",
                action=evaluate_readiness,
                result_key="report",
            ),
            WorkflowStep(
                name="write_readiness_artifacts",
                action=write_readiness_artifacts,
                result_key="artifacts",
            ),
        ),
    )

    try:
        trace_artifact = TraceWriter().write(execution.trace, output_dir)
    except Exception:
        if execution.trace.status is WorkflowStatus.FAILED:
            raise ScanWorkflowError(
                trace=execution.trace,
                trace_artifact=None,
            ) from None
        raise

    if execution.trace.status is WorkflowStatus.FAILED:
        raise ScanWorkflowError(
            trace=execution.trace,
            trace_artifact=trace_artifact,
        )

    return ScanResult(
        report=cast(ReadinessReport, execution.context["report"]),
        artifacts=(
            *cast(tuple[Artifact, ...], execution.context["artifacts"]),
            trace_artifact,
        ),
        trace=execution.trace,
    )
