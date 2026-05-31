from datetime import datetime, timezone

from agentops.core.workflow import WorkflowEventType, WorkflowStatus
from agentops.runtime.workflow import WorkflowRunner, WorkflowStep

FIXED_TIME = datetime(2026, 5, 31, tzinfo=timezone.utc)


def fail_with_value_error(context: dict[str, object]) -> object:
    raise ValueError("demo failure")


def test_workflow_runner_executes_steps_in_order() -> None:
    runner = WorkflowRunner(
        workflow_id_factory=lambda: "wf_demo",
        clock=lambda: FIXED_TIME,
    )
    execution = runner.run(
        workflow_name="demo",
        steps=(
            WorkflowStep(
                name="first",
                action=lambda context: "one",
                result_key="first_result",
            ),
            WorkflowStep(
                name="second",
                action=lambda context: context["first_result"] + "-two",
                result_key="second_result",
            ),
        ),
    )

    assert execution.context["second_result"] == "one-two"
    assert execution.trace.status is WorkflowStatus.COMPLETED
    assert [event.event_type for event in execution.trace.events] == [
        WorkflowEventType.WORKFLOW_STARTED,
        WorkflowEventType.STEP_STARTED,
        WorkflowEventType.STEP_COMPLETED,
        WorkflowEventType.STEP_STARTED,
        WorkflowEventType.STEP_COMPLETED,
        WorkflowEventType.WORKFLOW_COMPLETED,
    ]


def test_workflow_runner_stops_after_required_step_failure() -> None:
    runner = WorkflowRunner(
        workflow_id_factory=lambda: "wf_demo",
        clock=lambda: FIXED_TIME,
    )
    execution = runner.run(
        workflow_name="demo",
        steps=(
            WorkflowStep(name="prepare", action=lambda context: "ready", result_key="state"),
            WorkflowStep(name="required_failure", action=fail_with_value_error),
            WorkflowStep(name="must_not_run", action=lambda context: "unexpected"),
        ),
    )

    assert execution.context == {"state": "ready"}
    assert execution.trace.status is WorkflowStatus.FAILED
    assert execution.trace.failures[0].step_name == "required_failure"
    assert execution.trace.failures[0].recoverable is False
    assert [event.event_type for event in execution.trace.events][-2:] == [
        WorkflowEventType.STEP_FAILED,
        WorkflowEventType.WORKFLOW_FAILED,
    ]
    assert all(event.step_name != "must_not_run" for event in execution.trace.events)


def test_workflow_runner_continues_after_optional_step_failure() -> None:
    runner = WorkflowRunner(
        workflow_id_factory=lambda: "wf_demo",
        clock=lambda: FIXED_TIME,
    )
    execution = runner.run(
        workflow_name="demo",
        steps=(
            WorkflowStep(
                name="optional_failure",
                action=fail_with_value_error,
                required=False,
            ),
            WorkflowStep(name="finish", action=lambda context: "done", result_key="result"),
        ),
    )

    assert execution.context["result"] == "done"
    assert execution.trace.status is WorkflowStatus.COMPLETED_WITH_WARNINGS
    assert execution.trace.failures[0].recoverable is True
    assert execution.trace.events[-1].event_type is WorkflowEventType.WORKFLOW_COMPLETED
