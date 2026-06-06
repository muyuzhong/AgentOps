"""编排仓库记忆投影：读历史 → 装配投影 → 写产物，并保留 trace。

run_memory 是 Phase 5 的只读记忆流水线：逐行读 append-only 的 ``eval-history.jsonl``，
把累积评测确定性地投影为 ``RepoMemory``（趋势 + 失败模式 + 规则候选 + skill 候选），
再覆盖写出三个记忆产物。默认叙述者确定性、不触网、不需 key；记忆从不重算、扣减或
写回任何评测分数。编排沿用与 ``run_scan`` / ``run_eval`` 相同的 ``WorkflowRunner`` 与
trace 语义：步骤顺序固定、每步状态写入 trace，失败时保留可解释的部分结果。

``timestamp`` 可注入为统一工作流时钟，让 trace 也变得确定可复现（默认取当前 UTC）。
缺失历史文件或零条可用记录交由 ``read_history`` 步骤显式失败，并附"先跑 agentops eval"
的指引——上层据此转成结构化 ``MemoryWorkflowError``。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from agentops.core.artifact import Artifact
from agentops.core.memory import RepoMemory
from agentops.core.workflow import WorkflowStatus, WorkflowTrace
from agentops.memory import build_repo_memory
from agentops.memory.narrator import MemoryNarrator
from agentops.parsers.history import EvalHistoryReader, HistoryRecord
from agentops.runtime.workflow import WorkflowRunner, WorkflowStep
from agentops.writers.memory_report import MemoryReportWriter
from agentops.writers.trace import TraceWriter


@dataclass(frozen=True)
class MemoryRunResult:
    """聚合一次仓库记忆投影的结构化结果和产物。"""

    memory: RepoMemory
    artifacts: tuple[Artifact, ...]
    trace: WorkflowTrace


class MemoryWorkflowError(RuntimeError):
    """暴露记忆流程失败时保留下来的 workflow trace（沿用 scan/eval 语义）。"""

    def __init__(
        self,
        *,
        trace: WorkflowTrace,
        trace_artifact: Artifact | None,
    ) -> None:
        failed_step = trace.failures[0].step_name if trace.failures else "unknown"
        super().__init__(f"memory workflow failed at step: {failed_step}")
        self.trace = trace
        self.trace_artifact = trace_artifact


def run_memory(
    repo_path: Path,
    history_path: Path,
    output_dir: Path,
    *,
    narrator: MemoryNarrator | None = None,
    timestamp: datetime | None = None,
) -> MemoryRunResult:
    """编排 read_history → build_memory → write_memory_artifacts。"""

    reader = EvalHistoryReader()
    report_writer = MemoryReportWriter()

    def read_history(context: dict[str, object]) -> tuple[HistoryRecord, ...]:
        # 缺失文件由 runtime 显式转成结构化错误（reader 自身不处理缺失）。
        if not history_path.exists():
            raise FileNotFoundError(
                f"eval history not found: {history_path}; run agentops eval first"
            )
        records = reader.read(history_path)
        if not records:
            raise ValueError(
                f"eval history has no usable records: {history_path}; "
                "run agentops eval first"
            )
        return records

    def build_memory(context: dict[str, object]) -> RepoMemory:
        records = cast("tuple[HistoryRecord, ...]", context["records"])
        return build_repo_memory(
            records, repo_root=str(repo_path), narrator=narrator
        )

    def write_memory_artifacts(context: dict[str, object]) -> tuple[Artifact, ...]:
        return report_writer.write(cast(RepoMemory, context["memory"]), output_dir)

    # 注入固定时钟时连 trace 也确定可复现；默认走 runner 自带的 UTC 时钟。
    runner = (
        WorkflowRunner(clock=lambda: timestamp)
        if timestamp is not None
        else WorkflowRunner()
    )
    # 编排层只维护步骤顺序；读取、投影、写出细节留在各自模块。
    execution = runner.run(
        workflow_name="repo_memory",
        steps=(
            WorkflowStep(
                name="read_history",
                action=read_history,
                result_key="records",
            ),
            WorkflowStep(
                name="build_memory",
                action=build_memory,
                result_key="memory",
            ),
            WorkflowStep(
                name="write_memory_artifacts",
                action=write_memory_artifacts,
                result_key="artifacts",
            ),
        ),
    )

    try:
        trace_artifact = TraceWriter().write(execution.trace, output_dir)
    except Exception:
        if execution.trace.status is WorkflowStatus.FAILED:
            raise MemoryWorkflowError(
                trace=execution.trace,
                trace_artifact=None,
            ) from None
        raise

    if execution.trace.status is WorkflowStatus.FAILED:
        raise MemoryWorkflowError(
            trace=execution.trace,
            trace_artifact=trace_artifact,
        )

    return MemoryRunResult(
        memory=cast(RepoMemory, execution.context["memory"]),
        artifacts=(
            *cast("tuple[Artifact, ...]", execution.context["artifacts"]),
            trace_artifact,
        ),
        trace=execution.trace,
    )
