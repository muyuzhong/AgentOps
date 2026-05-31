import json
from datetime import datetime, timezone
from pathlib import Path

from agentops.core.artifact import ArtifactKind
from agentops.core.workflow import (
    WorkflowEvent,
    WorkflowEventType,
    WorkflowStatus,
    WorkflowTrace,
)
from agentops.writers.trace import TraceWriter


def test_trace_writer_writes_utf8_json_artifact(tmp_path: Path) -> None:
    trace = WorkflowTrace(
        workflow_id="wf_demo",
        workflow_name="repo_scan",
        status=WorkflowStatus.COMPLETED,
        events=(
            WorkflowEvent(
                event_type=WorkflowEventType.WORKFLOW_COMPLETED,
                workflow_id="wf_demo",
                workflow_name="repo_scan",
                timestamp=datetime(2026, 5, 31, tzinfo=timezone.utc),
                metadata={"message": "扫描完成"},
            ),
        ),
    )

    artifact = TraceWriter().write(trace, tmp_path)

    assert artifact.kind is ArtifactKind.WORKFLOW_TRACE
    assert artifact.path == tmp_path / "agentops-trace.json"
    content = artifact.path.read_text(encoding="utf-8")
    assert content.endswith("\n")
    assert "扫描完成" in content
    assert content.startswith('{\n  "events": [')
    assert content.index('"events"') < content.index('"failures"')
    assert content.index('"failures"') < content.index('"status"')
    assert json.loads(content)["status"] == "completed"
