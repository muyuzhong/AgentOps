"""确定性工作流的状态、事件和追踪模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Mapping


class WorkflowStatus(str, Enum):
    """描述一次工作流执行的最终或中间状态。"""

    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"


class WorkflowEventType(str, Enum):
    """工作流运行时会向 trace 写入的生命周期事件。"""

    WORKFLOW_STARTED = "workflow_started"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"


@dataclass(frozen=True)
class StepFailure:
    """保存单个步骤失败的稳定诊断信息。"""

    step_name: str
    error_type: str
    message: str
    recoverable: bool

    def to_dict(self) -> dict[str, object]:
        """转换为 JSON 友好的失败结构。"""

        return {
            "step_name": self.step_name,
            "error_type": self.error_type,
            "message": self.message,
            "recoverable": self.recoverable,
        }


@dataclass(frozen=True)
class WorkflowEvent:
    """记录工作流生命周期中的一次可观测状态变化。"""

    event_type: WorkflowEventType
    workflow_id: str
    workflow_name: str
    timestamp: datetime
    step_name: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """转换为 JSON 友好的事件结构。"""

        return {
            "event_type": self.event_type.value,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "timestamp": self.timestamp.isoformat(),
            "step_name": self.step_name,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class WorkflowTrace:
    """聚合一次工作流执行产生的事件和失败信息。"""

    workflow_id: str
    workflow_name: str
    status: WorkflowStatus
    events: tuple[WorkflowEvent, ...] = ()
    failures: tuple[StepFailure, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """转换为 TraceWriter 可以直接写出的结构。"""

        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "events": [event.to_dict() for event in self.events],
            "failures": [failure.to_dict() for failure in self.failures],
        }
