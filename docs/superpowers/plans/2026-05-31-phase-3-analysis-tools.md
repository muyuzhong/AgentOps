# Phase 3 Analysis Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deterministic analysis-tool layer required by future session evaluation: initialize a repository with an AgentOps task-log protocol, collect bounded session evidence, and normalize git, diff, CI, shell-output, and pytest evidence.

**Architecture:** Phase 3 adds small immutable evidence models, explicit `agentops init`, and independent read-only analyzers and parsers. Coding agents append short reports to `.agentops/agentops-session.md`; the parser keeps only bounded structured evidence and explicit references to optional raw transcripts. The future Phase 4 `agentops eval` workflow will consume these structures without loading full chat history by default.

**Tech Stack:** Python 3.11+, standard library `argparse`, `collections`, `dataclasses`, `enum`, `pathlib`, `re`, `subprocess`, `sys`, `pytest`, `PyYAML`

---

## Prerequisite

Complete:

```text
docs/superpowers/plans/2026-05-31-phase-2-workflow-runtime.md
```

Read the approved design:

```text
docs/superpowers/specs/2026-05-31-phase-3-analysis-tools-design.md
```

Confirm the baseline:

```powershell
python -m pytest -v
```

Expected before Phase 3 work begins:

```text
50 passed
```

## Scope Guard

Implement only deterministic initialization, evidence collection, and parsing.

Do not add:

- `agentops eval`.
- Session quality scores.
- Diagnosis or recommendation rules.
- LLM calls or LLM-based summarization.
- Full-transcript ingestion as the default path.
- Watcher processes.
- Async or parallel workflow execution.
- Automatic edits to application source code.
- Intelligent `CLAUDE.md` or `AGENTS.md` rewriting.
- Repository memory or historical trend storage.

`agentops init` is an explicit repository-write command. Existing `agentops scan` behavior must remain read-only.

## User-Visible Result

After Phase 3:

```powershell
agentops init --repo <repo-path>
```

asks an interactive user:

```text
How should AgentOps handle its session log?

1. Keep it private and ignore agentops-session.md (recommended)
2. Track it in Git for team sharing
3. Leave Git handling unmanaged
```

Automation can skip the prompt:

```powershell
agentops init --repo <repo-path> --session-log-policy private
agentops init --repo <repo-path> --session-log-policy tracked
agentops init --repo <repo-path> --session-log-policy unmanaged
```

When stdin is not interactive and the option is omitted, default to:

```text
private
```

Initialization always creates or refreshes:

```text
<repo-path>/
  .agentops/
    session-protocol.md
    agentops-session.md
```

Depending on the selected policy, it may also create or update:

```text
<repo-path>/
  .agentops/
    .gitignore
```

It also appends or refreshes a managed AgentOps block:

- in `CLAUDE.md` when it exists;
- in `AGENTS.md` when it exists;
- in both files when both exist;
- in `rule.md` when neither exists.

The new parser layer exposes reusable Python APIs for Phase 4. Phase 3 does not expose `agentops eval`.

## Target File Structure

```text
agentops/
  cli.py
  analyzers/
    __init__.py
    git.py
  core/
    __init__.py
    evidence.py
    repo.py
    session.py
  initializers/
    __init__.py
    repo.py
  parsers/
    __init__.py
    diff.py
    shell_output.py
    transcript.py
  scanners/
    __init__.py
    ci.py
    repo.py
tests/
  test_ci_scanner.py
  test_cli.py
  test_diff_parser.py
  test_evidence_models.py
  test_git_analyzer.py
  test_repo_initializer.py
  test_repo_scanner.py
  test_session_models.py
  test_shell_output_parser.py
  test_transcript_parser.py
```

## Evidence Contracts

### Repository Initialization

Expose:

```python
class SessionLogPolicy(str, Enum):
    PRIVATE = "private"
    TRACKED = "tracked"
    UNMANAGED = "unmanaged"


@dataclass(frozen=True)
class InitResult:
    repo_path: Path
    session_log_policy: SessionLogPolicy
    changed_paths: tuple[Path, ...]


def run_init(repo_path: Path, session_log_policy: SessionLogPolicy) -> InitResult:
    ...
```

`run_init()` is deterministic and does not prompt. The CLI resolves interactive input before calling it.

### Diff And Git Evidence

Expose:

```python
class ChangeKind(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass(frozen=True)
class ChangedFile:
    path: str
    change_kind: ChangeKind
    additions: int
    deletions: int
    previous_path: str | None = None


@dataclass(frozen=True)
class DiffSummary:
    files: tuple[ChangedFile, ...]
    additions: int
    deletions: int


@dataclass(frozen=True)
class GitStatus:
    repo_root: Path
    branch: str | None
    changed_paths: tuple[str, ...]
    untracked_paths: tuple[str, ...]
```

`DiffParser` consumes unified diff text. `GitAnalyzer` invokes local `git` with argument lists and `shell=False`.

### CI Evidence

Expose:

```python
@dataclass(frozen=True)
class CIProfile:
    config_files: tuple[str, ...]
    validation_commands: tuple[str, ...]
```

Extend:

```python
@dataclass(frozen=True)
class RepoProfile:
    ...
    validation_commands: tuple[str, ...] = ()
```

Use `yaml.safe_load()` for supported YAML files. Do not build a general workflow engine.

### Shell And Test Evidence

Expose:

```python
@dataclass(frozen=True)
class TestResult:
    framework: str
    passed: int | None = None
    failed: int | None = None
    skipped: int | None = None
    errors: int | None = None
    succeeded: bool | None = None


@dataclass(frozen=True)
class ShellResult:
    command: str
    exit_code: int
    succeeded: bool
    summary: str
    truncated: bool = False
    test_result: TestResult | None = None
```

Recognize common pytest terminal summaries. Unknown output stays unknown; do not guess.

### Bounded Session Evidence

Expose:

```python
@dataclass(frozen=True)
class VerificationRecord:
    command: str
    result: str


@dataclass(frozen=True)
class TaskReport:
    title: str
    goal: str
    context_used: tuple[str, ...] = ()
    changes: tuple[str, ...] = ()
    verification: tuple[VerificationRecord, ...] = ()
    issues: tuple[str, ...] = ()
    evidence_references: tuple[str, ...] = ()
    truncated: bool = False


@dataclass(frozen=True)
class SessionTrace:
    source_path: Path
    tasks: tuple[TaskReport, ...]
    truncated: bool = False
```

The parser reads `.agentops/agentops-session.md`, never raw transcripts.

Use explicit implementation constants:

```python
MAX_TASKS = 100
MAX_TASK_BYTES = 16_384
MAX_FIELD_CHARS = 2_000
MAX_LIST_ITEMS = 50
```

Retain the newest `MAX_TASKS` reports in source order. Mark truncation whenever earlier reports, list items, bytes, or field characters are dropped.

## Task 1: Define deterministic evidence models

**Files:**
- Create: `agentops/core/evidence.py`
- Modify: `agentops/core/__init__.py`
- Create: `tests/test_evidence_models.py`

- [ ] **Step 1: Write failing serialization tests**

Cover:

```python
def test_diff_summary_serializes_changed_files() -> None:
    summary = DiffSummary(
        files=(
            ChangedFile(
                path="src/app.py",
                change_kind=ChangeKind.MODIFIED,
                additions=3,
                deletions=1,
            ),
        ),
        additions=3,
        deletions=1,
    )

    assert summary.to_dict() == {
        "files": [
            {
                "path": "src/app.py",
                "change_kind": "modified",
                "additions": 3,
                "deletions": 1,
                "previous_path": None,
            },
        ],
        "additions": 3,
        "deletions": 1,
    }
```

Also require stable `to_dict()` output for:

- `GitStatus`;
- `CIProfile`;
- `ShellResult`;
- nested `TestResult`.

- [ ] **Step 2: Add validation tests**

Reject negative diff line counts:

```python
with pytest.raises(ValueError, match="line counts must be non-negative"):
    ChangedFile(
        path="src/app.py",
        change_kind=ChangeKind.MODIFIED,
        additions=-1,
        deletions=0,
    )
```

Reject negative recognized test counts with:

```text
test counts must be non-negative
```

- [ ] **Step 3: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_evidence_models.py -v
```

Expected: FAIL because `agentops.core.evidence` does not exist.

- [ ] **Step 4: Implement immutable evidence models**

Use frozen dataclasses and explicit `to_dict()` methods. Convert:

- `Path` to `str`;
- tuples to lists;
- enum members to `.value`;
- nested dataclasses through their own `to_dict()`.

Keep serialization stable and JSON friendly.

- [ ] **Step 5: Export public evidence types**

Update `agentops/core/__init__.py`.

- [ ] **Step 6: Run tests**

Run:

```powershell
python -m pytest tests/test_evidence_models.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add agentops/core tests/test_evidence_models.py
git commit -m "feat: define analysis evidence models"
```

## Task 2: Define bounded session models

**Files:**
- Create: `agentops/core/session.py`
- Modify: `agentops/core/__init__.py`
- Create: `tests/test_session_models.py`

- [ ] **Step 1: Write failing session-model tests**

Require:

```python
def test_session_trace_serializes_bounded_task_reports(tmp_path: Path) -> None:
    trace = SessionTrace(
        source_path=tmp_path / ".agentops" / "agentops-session.md",
        tasks=(
            TaskReport(
                title="Fix login error",
                goal="Return 401 for expired tokens.",
                context_used=("src/auth.py",),
                changes=("Adjust expired-token mapping.",),
                verification=(
                    VerificationRecord(
                        command="python -m pytest tests/test_auth.py -v",
                        result="3 passed",
                    ),
                ),
                evidence_references=("Transcript: evt_018-evt_031",),
            ),
        ),
    )

    data = trace.to_dict()
    assert data["tasks"][0]["title"] == "Fix login error"
    assert data["tasks"][0]["verification"][0]["result"] == "3 passed"
```

Also require serialized `truncated` fields on `TaskReport` and `SessionTrace`.

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_session_models.py -v
```

Expected: FAIL because `agentops.core.session` does not exist.

- [ ] **Step 3: Implement immutable session models**

Define:

- `VerificationRecord`;
- `TaskReport`;
- `SessionTrace`.

Use explicit stable `to_dict()` methods.

- [ ] **Step 4: Export public session types**

Update `agentops/core/__init__.py`.

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/test_session_models.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add agentops/core tests/test_session_models.py
git commit -m "feat: define bounded session evidence models"
```

## Task 3: Implement repository initialization

**Files:**
- Create: `agentops/initializers/__init__.py`
- Create: `agentops/initializers/repo.py`
- Create: `tests/test_repo_initializer.py`

- [ ] **Step 1: Write failing initialization tests**

Require `run_init()` to:

- reject a missing repository directory;
- create `.agentops/session-protocol.md`;
- create `.agentops/agentops-session.md` only when absent;
- preserve existing session-log content;
- add the managed instruction block to `CLAUDE.md` when only `CLAUDE.md` exists;
- add the block to `AGENTS.md` when only `AGENTS.md` exists;
- add the block to both when both exist;
- create or update `rule.md` when neither exists;
- preserve unrelated content in every instruction file;
- remain idempotent across repeated runs.

Use markers:

```python
INSTRUCTION_BLOCK_START = "<!-- agentops:session-protocol:start -->"
INSTRUCTION_BLOCK_END = "<!-- agentops:session-protocol:end -->"
```

Require the block to tell coding agents:

```text
完成每个独立开发任务后，请按 `.agentops/session-protocol.md` 的格式，
向 `.agentops/agentops-session.md` 追加简短汇报。
```

- [ ] **Step 2: Write failing session-log policy tests**

For `SessionLogPolicy.PRIVATE`, require `.agentops/.gitignore` to contain exactly one managed block:

```text
# agentops:session-log:start
agentops-session.md
# agentops:session-log:end
```

For `TRACKED`, remove only the AgentOps-managed ignore block.

For `UNMANAGED`, do not modify `.agentops/.gitignore`.

Do not modify the repository-root `.gitignore`. If it already ignores the whole `.agentops/` directory, `TRACKED` removes only the AgentOps-managed session-log rule and leaves broader repository policy to the user.

Preserve unrelated ignore rules for every policy.

- [ ] **Step 3: Write failing malformed-marker tests**

Require `run_init()` to reject:

- an instruction file with only one instruction-block marker;
- `.agentops/.gitignore` with only one AgentOps session-log marker;
- a selected instruction path that exists as a directory.

Use precise messages:

```text
managed block markers are malformed
instruction path must be a regular file
```

Verify malformed files remain byte-identical after failure.

- [ ] **Step 4: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_repo_initializer.py -v
```

Expected: FAIL because `agentops.initializers` does not exist.

- [ ] **Step 5: Implement initialization constants and models**

Define:

```python
class SessionLogPolicy(str, Enum):
    PRIVATE = "private"
    TRACKED = "tracked"
    UNMANAGED = "unmanaged"


@dataclass(frozen=True)
class InitResult:
    repo_path: Path
    session_log_policy: SessionLogPolicy
    changed_paths: tuple[Path, ...]
```

Keep the protocol template and managed blocks as module constants.

- [ ] **Step 6: Implement safe managed-block replacement**

Before writing:

1. validate all selected paths;
2. reject malformed marker pairs;
3. render all target contents in memory;
4. write only after validation succeeds.

For managed text files, write through a sibling temporary file and replace the destination. Preserve UTF-8 and a trailing newline.

Collapse duplicate complete AgentOps blocks into one canonical block. Never remove unrelated user text.

- [ ] **Step 7: Implement `run_init()`**

Sequence:

```text
validate repository
-> choose CLAUDE.md and AGENTS.md, or fallback rule.md
-> validate managed files
-> render session protocol
-> preserve or create agentops-session.md
-> apply selected .agentops/.gitignore policy
-> append or refresh instruction blocks
-> return sorted changed paths
```

Create `.agentops/` only after path validation passes.

- [ ] **Step 8: Run tests**

Run:

```powershell
python -m pytest tests/test_repo_initializer.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

Run:

```powershell
git add agentops/initializers tests/test_repo_initializer.py
git commit -m "feat: initialize repository session protocol"
```

## Task 4: Expose `agentops init` in the CLI

**Files:**
- Modify: `agentops/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing explicit-policy CLI tests**

Require:

```python
exit_code = main([
    "init",
    "--repo",
    str(repo_path),
    "--session-log-policy",
    "private",
])

assert exit_code == 0
assert (repo_path / ".agentops" / "session-protocol.md").exists()
assert (repo_path / ".agentops" / "agentops-session.md").exists()
```

Assert stdout names changed paths.

- [ ] **Step 2: Write failing interactive CLI tests**

Extract a small policy resolver:

```python
def resolve_session_log_policy(
    explicit_policy: SessionLogPolicy | None,
    *,
    stdin_isatty: bool,
    input_fn: Callable[[str], str] = input,
) -> SessionLogPolicy:
    ...
```

Require:

- explicit policy skips prompting;
- non-interactive stdin defaults to `PRIVATE`;
- interactive input `1` returns `PRIVATE`;
- interactive input `2` returns `TRACKED`;
- interactive input `3` returns `UNMANAGED`;
- unsupported answers prompt again.

- [ ] **Step 3: Write failing CLI error test**

Require a missing repository path to:

- return exit code `1`;
- print a concise initialization error to `stderr`;
- avoid a traceback.

Catch only the structured initializer error. Do not hide unexpected exceptions.

- [ ] **Step 4: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_cli.py -v
```

Expected: FAIL because the CLI does not expose `init`.

- [ ] **Step 5: Add parser arguments**

Add:

```text
agentops init --repo <repo-path>
agentops init --repo <repo-path> --session-log-policy private
agentops init --repo <repo-path> --session-log-policy tracked
agentops init --repo <repo-path> --session-log-policy unmanaged
```

Keep `scan` unchanged.

- [ ] **Step 6: Implement interactive policy resolution**

Print the three numbered choices only when:

- `--session-log-policy` is absent;
- stdin is interactive.

Default to `private` when stdin is not interactive.

- [ ] **Step 7: Run tests**

Run:

```powershell
python -m pytest tests/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```powershell
git add agentops/cli.py tests/test_cli.py
git commit -m "feat: expose repository initialization command"
```

## Task 5: Parse unified git diff evidence

**Files:**
- Create: `agentops/parsers/__init__.py`
- Create: `agentops/parsers/diff.py`
- Create: `tests/test_diff_parser.py`

- [ ] **Step 1: Write failing modified-file test**

Require:

```python
summary = DiffParser().parse(
    "\n".join([
        "diff --git a/src/app.py b/src/app.py",
        "--- a/src/app.py",
        "+++ b/src/app.py",
        "@@ -1,2 +1,3 @@",
        " old",
        "-before",
        "+after",
        "+extra",
    ])
)

assert summary.additions == 2
assert summary.deletions == 1
assert summary.files[0].path == "src/app.py"
assert summary.files[0].change_kind is ChangeKind.MODIFIED
```

- [ ] **Step 2: Add file-kind tests**

Cover:

- `new file mode` as `ADDED`;
- `deleted file mode` as `DELETED`;
- `rename from` and `rename to` as `RENAMED`;
- binary diff metadata with zero line counts;
- empty diff as an empty summary.

Ignore:

- `+++` and `---` headers when counting changed lines;
- `\ No newline at end of file`;
- hunk context lines.

- [ ] **Step 3: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_diff_parser.py -v
```

Expected: FAIL because `DiffParser` does not exist.

- [ ] **Step 4: Implement a line-oriented parser**

Parse only unified git diff metadata:

```text
diff --git
new file mode
deleted file mode
rename from
rename to
@@
+ added line
- deleted line
```

Do not invoke git inside the parser. Keep source order stable.

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/test_diff_parser.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add agentops/parsers tests/test_diff_parser.py
git commit -m "feat: parse unified git diff evidence"
```

## Task 6: Add read-only git analysis

**Files:**
- Create: `agentops/analyzers/__init__.py`
- Create: `agentops/analyzers/git.py`
- Create: `tests/test_git_analyzer.py`

- [ ] **Step 1: Write failing status test**

Create a temporary git repository:

```powershell
git init
git config user.email "agentops@example.com"
git config user.name "AgentOps Test"
```

Commit one file, then modify it and create an untracked file.

Require:

```python
status = GitAnalyzer().status(repo_path)

assert status.changed_paths == ("tracked.txt",)
assert status.untracked_paths == ("new.txt",)
```

Require sorted POSIX-style relative paths.

- [ ] **Step 2: Write failing diff test**

Require:

```python
summary = GitAnalyzer().diff(repo_path)

assert summary.files[0].path == "tracked.txt"
assert summary.files[0].change_kind is ChangeKind.MODIFIED
```

Use `DiffParser` for normalization.

- [ ] **Step 3: Add error tests**

Reject:

- a missing repository directory;
- a directory that is not a git repository;
- unavailable git executable.

Wrap subprocess failures in:

```python
class GitAnalysisError(RuntimeError):
    ...
```

- [ ] **Step 4: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_git_analyzer.py -v
```

Expected: FAIL because `GitAnalyzer` does not exist.

- [ ] **Step 5: Implement read-only git calls**

Use:

```python
subprocess.run(
    [...],
    cwd=repo_path,
    check=False,
    capture_output=True,
    text=True,
    shell=False,
)
```

Run only:

```text
git rev-parse --show-toplevel
git branch --show-current
git status --porcelain=v1 --untracked-files=all
git diff --find-renames --no-ext-diff --unified=0 HEAD
```

Do not mutate git config, index, commits, branches, or files.

- [ ] **Step 6: Run tests**

Run:

```powershell
python -m pytest tests/test_git_analyzer.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add agentops/analyzers tests/test_git_analyzer.py
git commit -m "feat: collect read-only git evidence"
```

## Task 7: Detect CI validation commands

**Files:**
- Modify: `pyproject.toml`
- Create: `agentops/scanners/ci.py`
- Modify: `agentops/scanners/repo.py`
- Modify: `agentops/scanners/__init__.py`
- Modify: `agentops/core/repo.py`
- Modify: `tests/test_core_models.py`
- Create: `tests/test_ci_scanner.py`
- Modify: `tests/test_repo_scanner.py`

- [ ] **Step 1: Write failing `RepoProfile` test**

Require:

```python
profile = RepoProfile(
    root=Path("demo"),
    validation_commands=("python -m pytest",),
)

assert profile.to_dict()["validation_commands"] == ["python -m pytest"]
```

- [ ] **Step 2: Write failing CI detection tests**

Cover:

- `.github/workflows/*.yml`;
- `.github/workflows/*.yaml`;
- `.gitlab-ci.yml`;
- `azure-pipelines.yml`;
- sorted relative config paths;
- file-only detection;
- malformed YAML with a precise scanner error.

- [ ] **Step 3: Write failing validation-command tests**

Use `yaml.safe_load()` and extract conservative command candidates from:

| CI provider | Supported locations |
| --- | --- |
| GitHub Actions | `jobs.*.steps[*].run` |
| GitLab CI | top-level `before_script`, `script`, `after_script`; job-level `before_script`, `script`, `after_script` |
| Azure Pipelines | `steps[*].script`, `steps[*].bash`, `steps[*].powershell`; `jobs[*].steps[*]` equivalents |

For multiline commands, split non-empty lines, strip whitespace, deduplicate, and preserve first-seen order.

Do not:

- expand environment variables;
- execute commands;
- interpret reusable workflows;
- follow includes;
- emulate CI provider behavior.

- [ ] **Step 4: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_core_models.py tests/test_ci_scanner.py tests/test_repo_scanner.py -v
```

Expected: FAIL because CI scanning and `validation_commands` do not exist.

- [ ] **Step 5: Add the YAML dependency**

Update:

```toml
dependencies = [
  "PyYAML>=6.0",
]
```

Install:

```powershell
python -m pip install -e ".[dev]"
```

- [ ] **Step 6: Implement `CIDetector`**

Expose:

```python
class CIScanError(RuntimeError):
    ...


class CIDetector:
    def scan(self, repo_path: Path) -> CIProfile:
        ...
```

Read only known CI paths and return stable config-file and validation-command tuples.

- [ ] **Step 7: Integrate CI profile into `RepoScanner`**

Keep existing `RepoProfile.ci_files` behavior stable. Add:

```python
validation_commands: tuple[str, ...] = ()
```

Set:

```python
ci_profile = CIDetector().scan(repo_path)
```

and copy:

- `ci_profile.config_files` to `RepoProfile.ci_files`;
- `ci_profile.validation_commands` to `RepoProfile.validation_commands`.

Do not remove conservative marker-based `test_commands`.

- [ ] **Step 8: Run tests**

Run:

```powershell
python -m pytest tests/test_core_models.py tests/test_ci_scanner.py tests/test_repo_scanner.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

Run:

```powershell
git add pyproject.toml agentops/core agentops/scanners tests
git commit -m "feat: detect CI validation commands"
```

## Task 8: Parse bounded shell output and pytest summaries

**Files:**
- Create: `agentops/parsers/shell_output.py`
- Modify: `agentops/parsers/__init__.py`
- Create: `tests/test_shell_output_parser.py`

- [ ] **Step 1: Write failing shell-summary tests**

Require:

```python
result = ShellOutputParser().parse(
    command="python -m pytest -v",
    exit_code=1,
    stdout="",
    stderr="AssertionError: expected 200, got 500",
)

assert result.command == "python -m pytest -v"
assert result.exit_code == 1
assert result.succeeded is False
assert "AssertionError" in result.summary
```

- [ ] **Step 2: Add bounded-output tests**

Define:

```python
MAX_SHELL_SUMMARY_CHARS = 4_000
```

Require oversized output to:

- retain a bounded head and tail;
- insert a deterministic truncation marker;
- set `truncated=True`;
- never exceed the documented limit plus marker length.

When both streams contain content, label them:

```text
[stdout]
...
[stderr]
...
```

- [ ] **Step 3: Add pytest-summary tests**

Recognize examples:

```text
3 passed in 0.12s
2 failed, 3 passed, 1 skipped in 0.44s
1 error in 0.08s
```

Require:

```python
assert result.test_result == TestResult(
    framework="pytest",
    passed=3,
    failed=2,
    skipped=1,
    errors=0,
    succeeded=False,
)
```

When output does not match a supported pytest summary:

```python
assert result.test_result is None
```

- [ ] **Step 4: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_shell_output_parser.py -v
```

Expected: FAIL because `ShellOutputParser` does not exist.

- [ ] **Step 5: Implement bounded shell normalization**

Use exit code for shell success:

```python
succeeded = exit_code == 0
```

Use deterministic truncation. Preserve enough head and tail text to keep the first diagnostic and final summary visible.

- [ ] **Step 6: Implement conservative pytest recognition**

Use explicit regular expressions for terminal summary counts. Do not infer unsupported frameworks yet.

- [ ] **Step 7: Run tests**

Run:

```powershell
python -m pytest tests/test_shell_output_parser.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```powershell
git add agentops/parsers tests/test_shell_output_parser.py
git commit -m "feat: parse bounded shell and pytest evidence"
```

## Task 9: Parse bounded AgentOps task logs

**Files:**
- Create: `agentops/parsers/transcript.py`
- Modify: `agentops/parsers/__init__.py`
- Create: `tests/test_transcript_parser.py`

- [ ] **Step 1: Write failing valid-log test**

Require:

```python
trace = TranscriptParser().parse(session_path)

assert len(trace.tasks) == 1
assert trace.tasks[0].title == "Fix login error"
assert trace.tasks[0].context_used == ("src/auth.py", "tests/test_auth.py")
assert trace.tasks[0].verification[0] == VerificationRecord(
    command="python -m pytest tests/test_auth.py -v",
    result="3 passed",
)
```

Use the protocol format:

```markdown
## Task: Fix login error

### Goal
Return 401 for expired tokens.

### Context Used
- `src/auth.py`
- `tests/test_auth.py`

### Changes
- Adjust expired-token mapping.

### Verification
- Command: `python -m pytest tests/test_auth.py -v`
- Result: `3 passed`

### Evidence References
- Transcript: `evt_018-evt_031`
```

- [ ] **Step 2: Add malformed-log tests**

Reject:

- missing task title;
- duplicate required section;
- missing `Goal`;
- missing `Changes`;
- missing `Verification`;
- `Result` without a preceding `Command`;
- `Command` without a following `Result`.

Expose:

```python
class TranscriptParseError(ValueError):
    ...
```

Errors should name the task and malformed section when possible.

- [ ] **Step 3: Add bounded-parsing tests**

Define:

```python
MAX_TASKS = 100
MAX_TASK_BYTES = 16_384
MAX_FIELD_CHARS = 2_000
MAX_LIST_ITEMS = 50
```

Require:

- only the newest `MAX_TASKS` task reports remain;
- retained reports preserve source order;
- dropped earlier tasks set `SessionTrace.truncated=True`;
- oversized free-text fields are clipped and set `TaskReport.truncated=True`;
- oversized lists retain the first `MAX_LIST_ITEMS` items and set `TaskReport.truncated=True`;
- a task larger than `MAX_TASK_BYTES` is rejected with:

```text
task report exceeds maximum size
```

- [ ] **Step 4: Add raw-transcript isolation test**

Create a large sibling raw transcript file and require parsing to succeed without reading it.

Use a monkeypatch or sentinel path object so any attempted raw-transcript read fails the test.

- [ ] **Step 5: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_transcript_parser.py -v
```

Expected: FAIL because `TranscriptParser` does not exist.

- [ ] **Step 6: Implement incremental report parsing**

Read the task log line by line. Keep:

- one in-progress task report;
- a bounded `deque(maxlen=MAX_TASKS)` of normalized reports;
- explicit truncation state.

Do not call `Path.read_text()` for the whole task log. Do not open referenced raw transcript files.

- [ ] **Step 7: Parse required and optional sections**

Required:

```text
Task
Goal
Changes
Verification
```

Optional:

```text
Context Used
Issues
Evidence References
```

Treat reference strings as opaque evidence pointers. Do not dereference them.

- [ ] **Step 8: Run tests**

Run:

```powershell
python -m pytest tests/test_transcript_parser.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

Run:

```powershell
git add agentops/parsers tests/test_transcript_parser.py
git commit -m "feat: parse bounded agentops task logs"
```

## Task 10: Update public and internal documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/development-roadmap.md`
- Modify: `docs/project-memory.md`
- Modify: `docs/README.md`
- Modify: `agent.md`

- [ ] **Step 1: Update GitHub README**

Keep README user-facing. Add:

```powershell
agentops init --repo <repo-path>
```

Explain briefly:

- it installs a short task-completion protocol;
- it preserves existing `CLAUDE.md` and `AGENTS.md` content;
- it lets users choose whether the session log remains private or is tracked.

Do not add internal parser details.

- [ ] **Step 2: Update architecture documentation**

Record:

- explicit repository initialization;
- bounded `.agentops/agentops-session.md`;
- raw transcript isolation;
- git, diff, CI, shell-output, and test evidence models;
- the Phase 3 boundary: parsing only, no scoring.

- [ ] **Step 3: Update roadmap and document index**

Mark Phase 3 complete only after implementation and verification pass.

Record Phase 4 as the next planning target:

```text
Session Eval
```

- [ ] **Step 4: Update cross-session memory**

Record:

- implemented files;
- test count;
- `agentops init`;
- session-log policy behavior;
- bounded parser limits;
- read-only git collection;
- supported CI extraction scope;
- supported pytest parsing scope;
- next step: write the Phase 4 plan.

- [ ] **Step 5: Commit**

Run:

```powershell
git add README.md agent.md docs
git commit -m "docs: record phase three analysis tools"
```

## Task 11: Verify Phase 3

- [ ] **Step 1: Install editable dependencies**

Run:

```powershell
python -m pip install -e ".[dev]"
```

Expected: editable install succeeds with `PyYAML`.

- [ ] **Step 2: Run all automated tests**

Run:

```powershell
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 3: Initialize a temporary repository with private logs**

Run:

```powershell
$demo = Join-Path $env:TEMP "agentops-phase3-private"
New-Item -ItemType Directory -Force -Path $demo | Out-Null
Set-Content -LiteralPath (Join-Path $demo "CLAUDE.md") -Value "# Existing rules"
Set-Content -LiteralPath (Join-Path $demo "AGENTS.md") -Value "# Shared rules"
agentops init --repo $demo --session-log-policy private
```

Expected:

- command exits with code `0`;
- `.agentops/session-protocol.md` exists;
- `.agentops/agentops-session.md` exists;
- `.agentops/.gitignore` ignores `agentops-session.md`;
- both `CLAUDE.md` and `AGENTS.md` preserve existing text and contain one managed block.

- [ ] **Step 4: Verify idempotent initialization**

Run:

```powershell
agentops init --repo $demo --session-log-policy private
```

Expected:

- command exits with code `0`;
- managed blocks are not duplicated;
- existing session-log content is preserved.

- [ ] **Step 5: Initialize a temporary repository without constraint files**

Run:

```powershell
$fallback = Join-Path $env:TEMP "agentops-phase3-fallback"
New-Item -ItemType Directory -Force -Path $fallback | Out-Null
agentops init --repo $fallback --session-log-policy unmanaged
```

Expected:

- `rule.md` exists;
- neither `CLAUDE.md` nor `AGENTS.md` is created;
- `.agentops/.gitignore` is not created.

- [ ] **Step 6: Confirm existing scan remains read-only**

Run:

```powershell
agentops scan --repo "D:\harness agent\agentops_harness" --output ".agentops\phase3-self-scan"
```

Expected:

- command exits with code `0`;
- readiness artifacts still exist;
- `agentops-trace.json` still reports `completed`;
- target repository source files remain unchanged.

- [ ] **Step 7: Confirm local artifacts remain ignored**

Run:

```powershell
git status --short --ignored
```

Expected: repository-local `.agentops/` outputs appear only as ignored files.

- [ ] **Step 8: Confirm a clean tracked worktree**

Run:

```powershell
git status --short
```

Expected: no output.

## Parallel Development Guidance

Start sequentially:

```text
evidence models
-> session models
-> repository initializer
-> init CLI
```

After Task 2 stabilizes public model contracts, the parser and analyzer branches can proceed in parallel:

| Worktree | Owns | Depends on |
| --- | --- | --- |
| `codex/diff-parser` | `agentops/parsers/diff.py`, `tests/test_diff_parser.py` | Task 1 |
| `codex/ci-detector` | `agentops/scanners/ci.py`, `agentops/scanners/repo.py`, `agentops/core/repo.py`, `pyproject.toml`, CI scanner tests | Task 1 |
| `codex/shell-output-parser` | `agentops/parsers/shell_output.py`, `tests/test_shell_output_parser.py` | Task 1 |
| `codex/transcript-parser` | `agentops/parsers/transcript.py`, `tests/test_transcript_parser.py` | Task 2 |

Implement `GitAnalyzer` after the diff parser:

| Worktree | Owns | Depends on |
| --- | --- | --- |
| `codex/git-analyzer` | `agentops/analyzers/git.py`, `tests/test_git_analyzer.py` | Task 5 |

Keep integration edits sequential:

- `agentops/core/__init__.py`;
- `agentops/parsers/__init__.py`;
- `agentops/scanners/__init__.py`;
- `agentops/cli.py`;
- `README.md`;
- `agent.md`;
- `docs/`;
- `docs/project-memory.md`.

Parallel worktrees must not update `docs/project-memory.md`. The integrator updates centralized memory after merging functional branches.

## Exit Criteria

Phase 3 is complete when:

- `agentops init --repo <repo-path>` installs a task-log protocol without overwriting user content.
- Interactive initialization asks whether the task log is private, tracked, or unmanaged.
- Non-interactive initialization defaults to a private session log.
- Simultaneous `CLAUDE.md` and `AGENTS.md` files both receive exactly one managed block.
- Repositories without either instruction file receive `rule.md`.
- Repeated initialization is idempotent.
- `.agentops/agentops-session.md` remains append-only during refresh.
- Session parsing retains bounded structured evidence and never loads raw transcript files.
- Git analysis is read-only.
- Unified diff parsing reports added, modified, deleted, and renamed files.
- CI scanning extracts only supported conservative validation commands.
- Shell-output parsing keeps bounded summaries and recognizes common pytest summaries.
- Existing `agentops scan` behavior remains read-only and green.
- `python -m pytest -v` passes.
