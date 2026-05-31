from datetime import datetime, timezone

from agentops.core.workflow import (
    StepFailure,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowStatus,
    WorkflowTrace,
)


def test_workflow_trace_serializes_nested_events_and_failures() -> None:
    timestamp = datetime(2026, 5, 31, tzinfo=timezone.utc)
    trace = WorkflowTrace(
        workflow_id="wf_demo",
        workflow_name="repo_scan",
        status=WorkflowStatus.FAILED,
        events=(
            WorkflowEvent(
                event_type=WorkflowEventType.STEP_FAILED,
                workflow_id="wf_demo",
                workflow_name="repo_scan",
                timestamp=timestamp,
                step_name="scan_repository",
                metadata={"error_type": "ValueError"},
            ),
        ),
        failures=(
            StepFailure(
                step_name="scan_repository",
                error_type="ValueError",
                message="repository directory does not exist",
                recoverable=False,
            ),
        ),
    )

    data = trace.to_dict()

    assert data["status"] == "failed"
    assert data["events"][0]["event_type"] == "step_failed"
    assert data["events"][0]["timestamp"] == "2026-05-31T00:00:00+00:00"
    assert data["events"][0]["metadata"] == {"error_type": "ValueError"}
    assert data["failures"][0]["recoverable"] is False
