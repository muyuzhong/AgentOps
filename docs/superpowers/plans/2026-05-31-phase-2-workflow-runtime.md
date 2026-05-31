# Phase 2 Workflow Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Phase 1 scan function into an observable deterministic workflow with explicit state, ordered events, failure isolation, graceful degradation, and a JSON trace artifact.

**Architecture:** Add a small synchronous `WorkflowRunner` shared by future AgentOps workflows. Each step writes structured lifecycle events into a `WorkflowTrace`. Required-step failures stop the workflow while preserving trace evidence; optional-step failures record warnings and allow later steps to continue. Retrofit `run_scan()` to use this runtime and write `.agentops/agentops-trace.json`.

**Tech Stack:** Python 3.11+, standard library `dataclasses`, `datetime`, `enum`, `json`, `pathlib`, `uuid`, `pytest`

---

## Prerequisite

Complete:

```text
docs/superpowers/plans/2026-05-30-phase-1-minimal-repo-scan.md
```

Confirm the baseline:

```powershell
python -m pytest -v
```

Expected before Phase 2 work begins:

```text
36 passed
```

## Scope Guard

Implement only the deterministic workflow runtime needed by current and near-term AgentOps workflows.

Do not add:

- Async execution.
- Parallel step execution.
- Persistent workflow storage.
- Resume or checkpoint support.
- Transcript parsing.
- LLM calls.
- Watcher processes.
- Supervisory Agent Loop.
- Generic plugin loading.

## User-Visible Result

After Phase 2:

```powershell
agentops scan --repo <repo-path> --output .agentops
```

still writes:

```text
.agentops/
  agentops-report.md
  agentops-score.json
```

and now also writes:

```text
.agentops/
  agentops-trace.json
```

The trace explains which steps ran, in what order, and whether the workflow completed or failed.

## Target File Structure

```text
agentops/
  cli.py
  core/
    __init__.py
    artifact.py
    workflow.py
  runtime/
    __init__.py
    scan.py
    workflow.py
  writers/
    __init__.py
    trace.py
tests/
  test_cli.py
  test_scan_runtime.py
  test_trace_writer.py
  test_workflow_models.py
  test_workflow_runtime.py
```

## Runtime Contract

The runtime must expose:

```python
WorkflowRunner.run(
    workflow_name: str,
    steps: tuple[WorkflowStep, ...],
    context: dict[str, object] | None = None,
) -> WorkflowExecution
```

Each `WorkflowStep`:

- has a stable `name`;
- calls a synchronous action with the shared mutable context;
- may save its return value under `result_key`;
- is required by default;
- may be marked optional to support graceful degradation.

The runner records:

```text
workflow_started
step_started
step_completed
step_failed
workflow_completed
workflow_failed
```

## Task 1: Define workflow state and trace models

**Files:**
- Create: `agentops/core/workflow.py`
- Modify: `agentops/core/__init__.py`
- Create: `tests/test_workflow_models.py`

- [x] **Step 1: Write failing model tests**

Cover:

```python
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
    assert data["failures"][0]["recoverable"] is False
```

Also test that trace metadata becomes an ordinary JSON-friendly dictionary.

- [x] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_workflow_models.py -v
```

Expected: FAIL because `agentops.core.workflow` does not exist.

- [x] **Step 3: Implement workflow enums**

Define:

```python
class WorkflowStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"


class WorkflowEventType(str, Enum):
    WORKFLOW_STARTED = "workflow_started"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
```

- [x] **Step 4: Implement trace dataclasses**

Define immutable dataclasses:

```python
@dataclass(frozen=True)
class StepFailure:
    step_name: str
    error_type: str
    message: str
    recoverable: bool

    def to_dict(self) -> dict[str, object]:
        ...


@dataclass(frozen=True)
class WorkflowEvent:
    event_type: WorkflowEventType
    workflow_id: str
    workflow_name: str
    timestamp: datetime
    step_name: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        ...


@dataclass(frozen=True)
class WorkflowTrace:
    workflow_id: str
    workflow_name: str
    status: WorkflowStatus
    events: tuple[WorkflowEvent, ...] = ()
    failures: tuple[StepFailure, ...] = ()

    def to_dict(self) -> dict[str, object]:
        ...
```

Use timezone-aware UTC timestamps. Convert metadata with `dict(self.metadata)` at the serialization boundary.

- [x] **Step 5: Export public workflow models**

Update `agentops/core/__init__.py`.

- [x] **Step 6: Run tests**

Run:

```powershell
python -m pytest tests/test_workflow_models.py -v
```

Expected: PASS.

- [x] **Step 7: Commit**

Run:

```powershell
git add agentops/core tests/test_workflow_models.py
git commit -m "feat: define workflow trace models"
```

## Task 2: Implement the deterministic workflow runner

**Files:**
- Create: `agentops/runtime/workflow.py`
- Modify: `agentops/runtime/__init__.py`
- Create: `tests/test_workflow_runtime.py`

- [x] **Step 1: Write failing success-path test**

Require:

```python
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
```

- [x] **Step 2: Write failing required-step failure test**

Require a required step exception to:

- become a `StepFailure(recoverable=False)`;
- stop later steps;
- produce `STEP_FAILED` and `WORKFLOW_FAILED`;
- return partial context without re-raising the original exception.

- [x] **Step 3: Write failing optional-step degradation test**

Require an optional step exception to:

- become a `StepFailure(recoverable=True)`;
- allow later steps to continue;
- produce final status `COMPLETED_WITH_WARNINGS`.

- [x] **Step 4: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_workflow_runtime.py -v
```

Expected: FAIL because `WorkflowRunner` does not exist.

- [x] **Step 5: Implement runtime dataclasses**

Define:

```python
@dataclass(frozen=True)
class WorkflowStep:
    name: str
    action: Callable[[dict[str, object]], object]
    result_key: str | None = None
    required: bool = True


@dataclass(frozen=True)
class WorkflowExecution:
    context: Mapping[str, object]
    trace: WorkflowTrace
```

- [x] **Step 6: Implement `WorkflowRunner`**

Constructor:

```python
class WorkflowRunner:
    def __init__(
        self,
        *,
        workflow_id_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        ...
```

Defaults:

- workflow ID: `wf_<uuid hex prefix>`;
- clock: timezone-aware UTC `datetime.now(timezone.utc)`.

Rules:

1. Copy the initial context into a new mutable dictionary.
2. Emit `WORKFLOW_STARTED`.
3. For each step, emit `STEP_STARTED`.
4. Store returned values only when `result_key` is not `None`.
5. Emit `STEP_COMPLETED` after success.
6. Convert exceptions into `StepFailure` and `STEP_FAILED`.
7. Stop after required-step failure and emit `WORKFLOW_FAILED`.
8. Continue after optional-step failure.
9. End with `WORKFLOW_COMPLETED`.
10. Set final status to `COMPLETED_WITH_WARNINGS` when recoverable failures exist.

Do not catch `BaseException`; catch `Exception`.

- [x] **Step 7: Export runtime types**

Update `agentops/runtime/__init__.py`.

- [x] **Step 8: Run tests**

Run:

```powershell
python -m pytest tests/test_workflow_runtime.py -v
```

Expected: PASS.

- [x] **Step 9: Commit**

Run:

```powershell
git add agentops/runtime tests/test_workflow_runtime.py
git commit -m "feat: add deterministic workflow runner"
```

## Task 3: Add JSON trace artifacts

**Files:**
- Modify: `agentops/core/artifact.py`
- Create: `agentops/writers/trace.py`
- Modify: `agentops/writers/__init__.py`
- Create: `tests/test_trace_writer.py`

- [x] **Step 1: Write failing trace writer test**

Require:

```python
artifact = TraceWriter().write(trace, output_dir)

assert artifact.kind is ArtifactKind.WORKFLOW_TRACE
assert artifact.path == output_dir / "agentops-trace.json"
assert json.loads(artifact.path.read_text(encoding="utf-8"))["status"] == "completed"
```

Also assert:

- UTF-8 JSON;
- trailing newline;
- `ensure_ascii=False`;
- `indent=2`;
- `sort_keys=True`.

- [x] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_trace_writer.py -v
```

Expected: FAIL because workflow trace artifacts do not exist.

- [x] **Step 3: Extend artifact kinds**

Add:

```python
WORKFLOW_TRACE = "workflow_trace"
```

- [x] **Step 4: Implement `TraceWriter`**

Define:

```python
class TraceWriter:
    def write(self, trace: WorkflowTrace, output_dir: Path) -> Artifact:
        ...
```

Write:

```text
agentops-trace.json
```

- [x] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/test_trace_writer.py -v
```

Expected: PASS.

- [x] **Step 6: Commit**

Run:

```powershell
git add agentops/core/artifact.py agentops/writers tests/test_trace_writer.py
git commit -m "feat: write workflow trace artifacts"
```

## Task 4: Retrofit `run_scan()` onto the workflow runtime

**Files:**
- Modify: `agentops/runtime/scan.py`
- Modify: `tests/test_scan_runtime.py`

- [x] **Step 1: Add failing scan trace test**

Require a successful scan to:

- return `ScanResult.trace`;
- include three named steps:
  - `scan_repository`;
  - `evaluate_readiness`;
  - `write_readiness_artifacts`;
- write `agentops-trace.json`;
- include the trace artifact in `ScanResult.artifacts`.

Expected ordered completed steps:

```python
[
    "scan_repository",
    "evaluate_readiness",
    "write_readiness_artifacts",
]
```

- [x] **Step 2: Add failing scan failure test**

Require a missing repository path to:

- produce a `ScanWorkflowError`;
- preserve a failed `WorkflowTrace`;
- write `agentops-trace.json` when the output directory is writable;
- record `scan_repository` as the failed step;
- skip evaluation and report writing.

- [x] **Step 3: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_scan_runtime.py -v
```

Expected: FAIL because scan does not use `WorkflowRunner`.

- [x] **Step 4: Extend `ScanResult`**

Define:

```python
@dataclass(frozen=True)
class ScanResult:
    report: ReadinessReport
    artifacts: tuple[Artifact, ...]
    trace: WorkflowTrace
```

- [x] **Step 5: Add structured scan failure**

Define:

```python
class ScanWorkflowError(RuntimeError):
    def __init__(
        self,
        *,
        trace: WorkflowTrace,
        trace_artifact: Artifact | None,
    ) -> None:
        ...
```

Expose the failed trace and optional trace artifact to callers.

- [x] **Step 6: Run scan through `WorkflowRunner`**

Use three required steps:

```text
scan_repository
evaluate_readiness
write_readiness_artifacts
```

After the workflow finishes:

1. write `agentops-trace.json`;
2. raise `ScanWorkflowError` when trace status is `FAILED`;
3. otherwise return `ScanResult`.

If trace writing fails after an earlier required-step failure, preserve the original workflow failure and set `trace_artifact=None`.

- [x] **Step 7: Update stability assertions**

Keep the existing target-repository read-only assertion.

Continue requiring deterministic Markdown and JSON readiness artifacts for repeated scans. Do not require byte-identical trace JSON because trace IDs and timestamps differ across runs.

- [x] **Step 8: Run tests**

Run:

```powershell
python -m pytest tests/test_scan_runtime.py -v
```

Expected: PASS.

- [x] **Step 9: Commit**

Run:

```powershell
git add agentops/runtime/scan.py tests/test_scan_runtime.py
git commit -m "feat: trace repository scan workflow"
```

## Task 5: Handle workflow failures in the CLI

**Files:**
- Modify: `agentops/cli.py`
- Modify: `tests/test_cli.py`

- [x] **Step 1: Add failing CLI success assertion**

Update scan CLI tests to require:

```text
agentops-trace.json
```

in the selected output directory.

- [x] **Step 2: Add failing CLI error test**

Require:

```python
exit_code = main([
    "scan",
    "--repo",
    str(tmp_path / "missing"),
    "--output",
    str(output_dir),
])

assert exit_code == 1
assert "scan_repository" in capsys.readouterr().err
assert (output_dir / "agentops-trace.json").exists()
```

- [x] **Step 3: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_cli.py -v
```

Expected: FAIL because CLI does not handle structured workflow failure.

- [x] **Step 4: Handle `ScanWorkflowError`**

Catch only `ScanWorkflowError`.

Print a concise error to `stderr`:

```text
AgentOps scan failed at step: <step-name>
```

If a trace artifact exists, also print:

```text
Wrote <trace-path>
```

Return exit code `1`.

- [x] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/test_cli.py -v
```

Expected: PASS.

- [x] **Step 6: Commit**

Run:

```powershell
git add agentops/cli.py tests/test_cli.py
git commit -m "feat: report scan workflow failures"
```

## Task 6: Update public and internal documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/development-roadmap.md`
- Modify: `docs/project-memory.md`
- Modify: `docs/README.md`
- Modify: `agent.md`

- [x] **Step 1: Update GitHub README**

Keep README user-facing. Add only:

- `agentops-trace.json` to output examples;
- one sentence explaining that it records workflow steps and failures.

Do not add internal implementation details.

- [x] **Step 2: Update architecture documentation**

Record:

- `WorkflowRunner`;
- `WorkflowTrace`;
- required and optional step behavior;
- the current scan step sequence.

- [x] **Step 3: Update roadmap and document index**

Mark Phase 2 complete only after implementation and verification pass.

- [x] **Step 4: Update cross-session memory**

Record:

- implemented files;
- test count;
- new CLI failure behavior;
- new trace artifact;
- next step: write Phase 3 plan.

- [x] **Step 5: Commit**

Run:

```powershell
git add README.md agent.md docs
git commit -m "docs: record workflow runtime architecture"
```

## Task 7: Verify Phase 2

- [x] **Step 1: Run all automated tests**

Run:

```powershell
python -m pytest -v
```

Expected: all tests pass.

- [x] **Step 2: Run a successful self-scan**

Run:

```powershell
agentops scan --repo "D:\harness agent\agentops_harness" --output ".agentops\self-scan"
```

Expected:

- command exits with code `0`;
- `agentops-report.md` exists;
- `agentops-score.json` exists;
- `agentops-trace.json` exists;
- trace status is `completed`.

- [x] **Step 3: Inspect the successful trace**

Run:

```powershell
Get-Content -LiteralPath ".agentops\self-scan\agentops-trace.json" -Encoding utf8
```

Expected: JSON contains ordered step events for scan, evaluate, and write.

- [x] **Step 4: Run a failing scan**

Run:

```powershell
agentops scan --repo ".\missing-repository" --output ".agentops\failed-scan"
```

Expected:

- command exits with code `1`;
- stderr names `scan_repository`;
- `.agentops/failed-scan/agentops-trace.json` exists;
- trace status is `failed`.

- [x] **Step 5: Confirm local artifacts remain ignored**

Run:

```powershell
git status --short --ignored
```

Expected: `.agentops/` appears only as ignored output.

- [x] **Step 6: Confirm a clean tracked worktree**

Run:

```powershell
git status --short
```

Expected: no output.

## Parallel Development Guidance

Phase 2 has a dependency chain. Prefer sequential implementation:

```text
workflow models
-> workflow runner
-> trace writer
-> scan integration
-> CLI integration
-> docs
```

Limited parallelism is possible after Task 1:

| Worktree | Owns | Depends on |
| --- | --- | --- |
| `codex/workflow-runner` | `agentops/runtime/workflow.py`, `tests/test_workflow_runtime.py` | Task 1 |
| `codex/trace-writer` | `agentops/core/artifact.py`, `agentops/writers/trace.py`, `tests/test_trace_writer.py` | Task 1 |

Keep scan integration and CLI integration sequential because they touch shared orchestration behavior.

## Exit Criteria

Phase 2 is complete when:

- `WorkflowRunner` emits ordered lifecycle events.
- Required-step failures stop the workflow and preserve a failed trace.
- Optional-step failures degrade to `completed_with_warnings`.
- `agentops scan` writes `agentops-trace.json`.
- Failed CLI scans return exit code `1` and preserve trace evidence when possible.
- Existing readiness artifacts remain deterministic.
- Target repositories remain read-only.
- `python -m pytest -v` passes.
