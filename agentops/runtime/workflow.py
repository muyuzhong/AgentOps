"""可观测且可降级的确定性工作流运行时。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping
from uuid import uuid4

from agentops.core.workflow import (
    StepFailure,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowStatus,
    WorkflowTrace,
)


@dataclass(frozen=True)
class WorkflowStep:
    """描述工作流中的一个同步步骤。"""

    name: str
    action: Callable[[dict[str, object]], object]
    result_key: str | None = None
    required: bool = True


@dataclass(frozen=True)
class WorkflowExecution:
    """保存工作流执行后的部分上下文和完整追踪。"""

    context: Mapping[str, object]
    trace: WorkflowTrace


class WorkflowRunner:
    """按照固定顺序执行步骤，并把状态变化写入 trace。"""

    def __init__(
        self,
        *,
        workflow_id_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._workflow_id_factory = workflow_id_factory or self._default_workflow_id
        self._clock = clock or self._utc_now

    def run(
        self,
        *,
        workflow_name: str,
        steps: tuple[WorkflowStep, ...],
        context: dict[str, object] | None = None,
    ) -> WorkflowExecution:
        """顺序执行步骤，并在失败时保留可解释的部分结果。"""

        workflow_id = self._workflow_id_factory()
        runtime_context = dict(context or {})
        events: list[WorkflowEvent] = []
        failures: list[StepFailure] = []
        self._append_event(
            events,
            event_type=WorkflowEventType.WORKFLOW_STARTED,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
        )

        for step in steps:
            self._append_event(
                events,
                event_type=WorkflowEventType.STEP_STARTED,
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                step_name=step.name,
            )
            try:
                result = step.action(runtime_context)
            except Exception as error:
                failure = StepFailure(
                    step_name=step.name,
                    error_type=type(error).__name__,
                    message=str(error),
                    recoverable=not step.required,
                )
                failures.append(failure)
                self._append_event(
                    events,
                    event_type=WorkflowEventType.STEP_FAILED,
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    step_name=step.name,
                    metadata=failure.to_dict(),
                )
                if step.required:
                    self._append_event(
                        events,
                        event_type=WorkflowEventType.WORKFLOW_FAILED,
                        workflow_id=workflow_id,
                        workflow_name=workflow_name,
                        metadata={"failed_step": step.name},
                    )
                    return WorkflowExecution(
                        context=runtime_context,
                        trace=WorkflowTrace(
                            workflow_id=workflow_id,
                            workflow_name=workflow_name,
                            status=WorkflowStatus.FAILED,
                            events=tuple(events),
                            failures=tuple(failures),
                        ),
                    )
                continue

            if step.result_key is not None:
                runtime_context[step.result_key] = result
            self._append_event(
                events,
                event_type=WorkflowEventType.STEP_COMPLETED,
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                step_name=step.name,
            )

        status = (
            WorkflowStatus.COMPLETED_WITH_WARNINGS
            if failures
            else WorkflowStatus.COMPLETED
        )
        self._append_event(
            events,
            event_type=WorkflowEventType.WORKFLOW_COMPLETED,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            metadata={"status": status.value},
        )
        return WorkflowExecution(
            context=runtime_context,
            trace=WorkflowTrace(
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                status=status,
                events=tuple(events),
                failures=tuple(failures),
            ),
        )

    def _append_event(
        self,
        events: list[WorkflowEvent],
        *,
        event_type: WorkflowEventType,
        workflow_id: str,
        workflow_name: str,
        step_name: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        """追加一个带统一时钟的运行时事件。"""

        events.append(
            WorkflowEvent(
                event_type=event_type,
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                timestamp=self._clock(),
                step_name=step_name,
                metadata=metadata or {},
            )
        )

    @staticmethod
    def _default_workflow_id() -> str:
        """生成便于日志关联的短工作流标识。"""

        return f"wf_{uuid4().hex[:12]}"

    @staticmethod
    def _utc_now() -> datetime:
        """返回带时区的 UTC 时间。"""

        return datetime.now(timezone.utc)
