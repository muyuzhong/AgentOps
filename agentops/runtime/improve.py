"""编排改进资产投影：读历史 → 装配记忆 → 读指令文件 → 投影资产 → 写产物，并保留 trace。

run_suggest 是 Phase 6 的只读 suggest 流水线：逐行读 append-only 的 eval-history.jsonl，
复用 Phase 5 把累积评测确定性地投影为 RepoMemory，再只读地读取仓库当前的
CLAUDE.md / AGENTS.md / README.md，把记忆 + 指令文件确定性地投影为 ImprovementAssets，
最后覆盖写出四个改进资产产物。默认叙述者确定性、不触网、不需 key；suggest 对目标仓库
只读（除 --output 外不写任何文件），从不重算、扣减或写回任何评测分数。

编排沿用 scan / eval / memory 相同的 WorkflowRunner 与 trace 语义：步骤顺序固定、每步状态
写入 trace，失败时保留可解释的部分结果。read_history / build_memory 完全复用 Phase 5——
含缺失文件 / 零条记录的结构化失败与“先跑 agentops eval”的指引。``timestamp`` 可注入为统一
工作流时钟，让 trace 也确定可复现（默认取当前 UTC）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from agentops.core.artifact import Artifact
from agentops.core.asset import ImprovementAssets
from agentops.core.memory import RepoMemory
from agentops.core.workflow import WorkflowStatus, WorkflowTrace
from agentops.improve import build_improvement_assets
from agentops.improve.narrator import AssetNarrator
from agentops.memory import build_repo_memory
from agentops.parsers.history import EvalHistoryReader, HistoryRecord
from agentops.runtime.workflow import WorkflowRunner, WorkflowStep
from agentops.writers.improvement_report import ImprovementReportWriter
from agentops.writers.trace import TraceWriter

# 只读读取的指令文件（缺失 → None，从不报错；suggest 绝不修改目标仓库）。
_INSTRUCTION_FILES = ("CLAUDE.md", "AGENTS.md")
_README_FILE = "README.md"


@dataclass(frozen=True)
class ImproveRunResult:
    """聚合一次改进资产投影的结构化结果和产物。"""

    assets: ImprovementAssets
    artifacts: tuple[Artifact, ...]
    trace: WorkflowTrace


class ImproveWorkflowError(RuntimeError):
    """暴露 suggest 流程失败时保留下来的 workflow trace（沿用 scan/eval/memory 语义）。"""

    def __init__(
        self,
        *,
        trace: WorkflowTrace,
        trace_artifact: Artifact | None,
    ) -> None:
        failed_step = trace.failures[0].step_name if trace.failures else "unknown"
        super().__init__(f"suggest workflow failed at step: {failed_step}")
        self.trace = trace
        self.trace_artifact = trace_artifact


def _read_optional(path: Path) -> str | None:
    """只读读取一个可选指令文件；缺失或非普通文件 → None，从不报错。"""

    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def run_suggest(
    repo_path: Path,
    history_path: Path,
    output_dir: Path,
    *,
    narrator: AssetNarrator | None = None,
    timestamp: datetime | None = None,
) -> ImproveRunResult:
    """编排 read_history → build_memory → read_instructions → build_assets → write_improvement_artifacts。"""

    reader = EvalHistoryReader()
    report_writer = ImprovementReportWriter()

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
        # 记忆叙述者保持默认确定性；suggest 的叙述接缝是 AssetNarrator（在 build_assets 注入）。
        return build_repo_memory(records, repo_root=str(repo_path))

    def read_instructions(context: dict[str, object]) -> dict[str, object]:
        # 只读读取目标仓库现有指令文件；缺失 → None，绝不修改仓库。
        instructions = {
            name: _read_optional(repo_path / name) for name in _INSTRUCTION_FILES
        }
        readme = _read_optional(repo_path / _README_FILE)
        return {"instructions": instructions, "readme": readme}

    def build_assets(context: dict[str, object]) -> ImprovementAssets:
        memory = cast(RepoMemory, context["memory"])
        bundle = cast("dict[str, object]", context["instructions_bundle"])
        instructions = cast("dict[str, str | None]", bundle["instructions"])
        readme = cast("str | None", bundle["readme"])
        return build_improvement_assets(
            memory,
            repo_root=str(repo_path),
            instructions=instructions,
            readme=readme,
            narrator=narrator,
        )

    def write_improvement_artifacts(
        context: dict[str, object],
    ) -> tuple[Artifact, ...]:
        return report_writer.write(
            cast(ImprovementAssets, context["assets"]), output_dir
        )

    # 注入固定时钟时连 trace 也确定可复现；默认走 runner 自带的 UTC 时钟。
    runner = (
        WorkflowRunner(clock=lambda: timestamp)
        if timestamp is not None
        else WorkflowRunner()
    )
    # 编排层只维护步骤顺序；读取、投影、写出细节留在各自模块。
    execution = runner.run(
        workflow_name="repo_suggest",
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
                name="read_instructions",
                action=read_instructions,
                result_key="instructions_bundle",
            ),
            WorkflowStep(
                name="build_assets",
                action=build_assets,
                result_key="assets",
            ),
            WorkflowStep(
                name="write_improvement_artifacts",
                action=write_improvement_artifacts,
                result_key="artifacts",
            ),
        ),
    )

    try:
        trace_artifact = TraceWriter().write(execution.trace, output_dir)
    except Exception:
        if execution.trace.status is WorkflowStatus.FAILED:
            raise ImproveWorkflowError(
                trace=execution.trace,
                trace_artifact=None,
            ) from None
        raise

    if execution.trace.status is WorkflowStatus.FAILED:
        raise ImproveWorkflowError(
            trace=execution.trace,
            trace_artifact=trace_artifact,
        )

    return ImproveRunResult(
        assets=cast(ImprovementAssets, execution.context["assets"]),
        artifacts=(
            *cast("tuple[Artifact, ...]", execution.context["artifacts"]),
            trace_artifact,
        ),
        trace=execution.trace,
    )
