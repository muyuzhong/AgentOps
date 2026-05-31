# Phase 3 Analysis Tools Design

## Goal

Phase 3 builds the deterministic evidence collection and parsing layer required by the future `agentops eval` workflow.

The phase adds:

- a minimal `agentops init --repo <repo-path>` command that installs a task-completion protocol before monitored work begins;
- bounded parsing for AgentOps task logs;
- git and diff analysis;
- CI and validation-command detection;
- shell-output and test-result parsing.

Phase 3 does not score a session, call an LLM, load full chat history by default, or expose `agentops eval`. Those belong to later phases.

## User-Visible Workflow

Before using an AI coding agent in a repository, the user runs:

```powershell
agentops init --repo <repo-path>
```

Interactive terminals ask how the repository should handle the generated session log:

```text
如何处理 AgentOps 会话日志？

1. 本地私有：忽略 agentops-session.md（推荐）
2. 提交 Git：保留会话日志供团队共享
3. 暂不设置：仅创建文件
```

Automation can select the same policy explicitly:

```powershell
agentops init --repo <repo-path> --session-log-policy private
agentops init --repo <repo-path> --session-log-policy tracked
agentops init --repo <repo-path> --session-log-policy unmanaged
```

When stdin is not interactive and the option is omitted, initialization defaults to `private`.

The initialized repository then asks coding agents to append a short structured report after every independent development task:

```text
coding task completes
-> coding agent appends a bounded report
-> .agentops/agentops-session.md grows incrementally
-> Phase 3 parsers normalize the short reports
-> Phase 4 evaluators consume the normalized evidence
```

The full raw transcript remains optional archival evidence. It is not the normal evaluation input. A later evaluator may retrieve a small raw excerpt only when a task report includes an explicit evidence reference and a concrete diagnosis needs deeper inspection.

## Scope Guard

Implement only deterministic evidence collection, initialization, and parsing.

Do not add:

- quality scores;
- diagnosis rules;
- `agentops eval`;
- LLM-based summarization;
- full-transcript ingestion as the default path;
- watcher processes;
- automatic edits to application source code;
- Phase 6 asset generation or intelligent rule rewriting.

## Initialization Contract

### Command

```powershell
agentops init --repo <repo-path>
```

Initialization is an explicit write operation. Existing `scan` behavior remains read-only.

### Files

The command always creates or refreshes:

```text
<repo-path>/
  .agentops/
    session-protocol.md
    agentops-session.md
```

`session-protocol.md` contains the canonical task-report template and instructions. `agentops-session.md` is the append-only task log consumed by the parser.

`.agentops/.gitignore` is created or updated only when required by the selected session-log policy:

| Policy | Behavior |
| --- | --- |
| `private` | Add a managed ignore rule for `agentops-session.md`. |
| `tracked` | Remove only the AgentOps-managed ignore rule so the log can be committed. |
| `unmanaged` | Do not change `.agentops/.gitignore`. |

When `.agentops/.gitignore` already exists, initialization preserves unrelated user rules. The initializer manages only its own marked block.

Initialization does not modify the repository-root `.gitignore`. If it already ignores the whole `.agentops/` directory, `tracked` removes only the AgentOps-managed session-log rule and leaves broader repository policy to the user.

The command also installs a concise managed reference block into repository-level agent instructions.

### Instruction File Selection

Use exact repository-root filenames:

```text
CLAUDE.md
AGENTS.md
rule.md
```

Selection rules:

1. If `CLAUDE.md` exists, update it.
2. If `AGENTS.md` exists, update it.
3. If both exist, update both.
4. If neither exists, create or update `rule.md`.
5. Never create `CLAUDE.md` or `AGENTS.md` automatically.
6. Never overwrite unrelated user content.

### Managed Block

Append or refresh exactly one managed block per selected instruction file:

```markdown
<!-- agentops:session-protocol:start -->
完成每个独立开发任务后，请按 `.agentops/session-protocol.md` 的格式，
向 `.agentops/agentops-session.md` 追加简短汇报。
<!-- agentops:session-protocol:end -->
```

Running `agentops init` repeatedly is idempotent:

- an existing valid managed block is replaced in place;
- unrelated content before and after the block is preserved;
- duplicate managed blocks are collapsed into one block;
- an existing `rule.md` is updated rather than overwritten when it is the selected fallback.
- an existing `.agentops/.gitignore` preserves unrelated ignore rules;
- the selected session-log policy updates only the AgentOps-managed ignore block.

The first version does not add `--refresh`. Re-running the same command refreshes AgentOps-managed content.

### Initialization Errors

Initialization fails clearly when:

- the repository path does not exist or is not a directory;
- a selected instruction path exists but is not a regular file;
- `.agentops` or a managed file cannot be written;
- a managed block has an opening marker without a closing marker, or vice versa.
- `--session-log-policy` is not one of `private`, `tracked`, or `unmanaged`.

The initializer must not silently partially rewrite an instruction file with malformed markers. Tests should use temporary repositories and verify preserved user content.

## Task Log Protocol

### Canonical Log

`.agentops/agentops-session.md` is an append-only sequence of task reports. Each report is intentionally short and independently parseable:

```markdown
## Task: 修复登录接口报错

### Goal
修复 token 过期时返回 500 的问题。

### Context Used
- `src/auth.py`
- `tests/test_auth.py`

### Changes
- 修正 token 过期分支的异常映射。
- 新增过期 token 回归测试。

### Verification
- Command: `python -m pytest tests/test_auth.py -v`
- Result: `3 passed`

### Issues
- 首次测试失败：响应码仍为 500。
- 调整异常映射后通过。

### Evidence References
- Transcript: `evt_018-evt_031`
- Diff: `src/auth.py`
```

Required sections:

- `Task`;
- `Goal`;
- `Changes`;
- `Verification`.

Optional sections:

- `Context Used`;
- `Issues`;
- `Evidence References`.

The protocol asks the coding agent to keep each section concise. It must reference raw transcript excerpts by event ID, line range, or external archive pointer rather than copying long chat history into the log.

### Bounded Parsing

The parser reads `agentops-session.md` incrementally and returns structured task reports. It must not load or summarize raw transcript files.

Apply deterministic limits:

- maximum bytes accepted for one task report;
- maximum retained characters for each free-text field;
- maximum number of list items retained per section;
- explicit truncation metadata when a limit is reached;
- stable ordering matching the source log.

The exact constants belong in implementation code and tests. They should be conservative enough to keep Phase 4 context bounded while still preserving useful evidence.

## Structured Evidence Models

Add small immutable models with stable `to_dict()` serialization.

### Session Evidence

```text
SessionTrace
  source_path
  tasks

TaskReport
  title
  goal
  context_used
  changes
  verification
  issues
  evidence_references
  truncated

VerificationRecord
  command
  result
```

`SessionTrace` represents the bounded task log, not the raw transcript.

### Diff Evidence

```text
DiffSummary
  files
  additions
  deletions

ChangedFile
  path
  change_kind
  additions
  deletions
```

Supported change kinds:

```text
added
modified
deleted
renamed
```

### Git Evidence

```text
GitStatus
  repo_root
  branch
  changed_paths
  untracked_paths
```

The git reader is read-only. It may call local `git` commands with argument lists and `shell=False`. It must preserve predictable errors when the target is not a git repository or git is unavailable.

### Shell And Test Evidence

```text
ShellResult
  command
  exit_code
  succeeded
  summary
  truncated

TestResult
  framework
  passed
  failed
  skipped
  errors
  succeeded
```

Shell-output parsing keeps a bounded summary. Test-result parsing initially recognizes common `pytest` summaries and preserves an `unknown` outcome when output does not match a supported format.

### CI Evidence

Extend repository scanning with deterministic CI and validation-command evidence:

```text
CIProfile
  config_files
  validation_commands
```

The first version recognizes known files and extracts conservative command candidates from supported CI YAML files. It does not execute CI pipelines or implement a general YAML workflow engine.

## Components

Suggested module boundaries:

```text
agentops/
  cli.py
  core/
    session.py
    evidence.py
  initializers/
    repo.py
  analyzers/
    git.py
  parsers/
    diff.py
    shell_output.py
    transcript.py
  scanners/
    ci.py
    repo.py
```

Responsibilities:

| Module | Responsibility |
| --- | --- |
| `core/session.py` | Bounded session-log models |
| `core/evidence.py` | Diff, git, CI, shell, and test evidence models |
| `initializers/repo.py` | Explicit repository initialization and managed-block updates |
| `analyzers/git.py` | Read-only local git status and diff collection |
| `parsers/diff.py` | Parse unified git diff text into stable summaries |
| `parsers/shell_output.py` | Normalize bounded shell summaries and supported test output |
| `parsers/transcript.py` | Parse `agentops-session.md` into `SessionTrace` |
| `scanners/ci.py` | Detect CI configuration and conservative validation commands |
| `scanners/repo.py` | Integrate CI profile data into repository scanning where appropriate |
| `cli.py` | Thin `init` command adapter |

The implementation plan may split or combine files when existing patterns make a smaller change clearer, but these ownership boundaries should remain intact.

## Data Flow

### Repository Initialization

```text
agentops init
-> validate repository path
-> resolve interactive or explicit session-log policy
-> write or refresh .agentops/session-protocol.md
-> create .agentops/agentops-session.md if absent
-> update the AgentOps-managed .agentops/.gitignore block when required
-> select existing CLAUDE.md and AGENTS.md, or fallback rule.md
-> append or refresh managed instruction blocks
-> print changed paths
```

### Phase 3 Analysis

```text
repository
-> GitReader
-> GitStatus + raw unified diff
-> DiffParser
-> DiffSummary

repository
-> CIDetector
-> CIProfile

shell command metadata + output
-> ShellOutputParser
-> ShellResult + optional TestResult

.agentops/agentops-session.md
-> TranscriptParser
-> SessionTrace
```

Phase 4 will combine these structures into an evaluation workflow.

## Error Handling

- Parsers reject malformed required structure with precise errors.
- Parsers preserve bounded evidence and mark truncation explicitly.
- Unsupported shell or test formats return stable unknown evidence rather than guessing.
- Git operations remain read-only and surface command failures clearly.
- `init` preserves unrelated content and rejects malformed managed markers.
- Partial initialization failures must be visible to the caller. The implementation plan should prefer validating all target paths before writing any file and use replace-style writes for managed text files.

## Testing Strategy

Use test-driven development and temporary repositories.

Cover:

- `init` creates `.agentops/session-protocol.md` and `.agentops/agentops-session.md`;
- interactive `init` asks for a session-log policy;
- non-interactive `init` defaults to `private`;
- `private` and `tracked` update only AgentOps-managed ignore rules, while `unmanaged` leaves ignore files unchanged;
- an existing `.agentops/.gitignore` preserves unrelated user content;
- `init` updates only `CLAUDE.md` when only that file exists;
- `init` updates only `AGENTS.md` when only that file exists;
- `init` updates both when both exist;
- `init` creates or preserves `rule.md` when neither exists;
- repeated `init` calls remain idempotent;
- malformed managed markers fail without losing user content;
- CLI `init` exposes concise success and failure behavior;
- unified diff parsing for added, modified, deleted, and renamed files;
- git reader behavior in a temporary git repository;
- CI detection and conservative validation-command extraction;
- bounded shell summaries;
- recognized and unknown test summaries;
- valid, malformed, and oversized `agentops-session.md` reports;
- stable `to_dict()` serialization;
- existing `scan` tests remain green and target scanning remains read-only.

## Documentation Updates

After Phase 3 implementation:

- add `agentops init` usage to the public `README.md`;
- document the session protocol and analysis-tool boundaries in `docs/architecture.md`;
- mark Phase 3 complete in `docs/development-roadmap.md`;
- update `docs/project-memory.md` with implemented files, verification results, and the Phase 4 next step;
- add the new Phase 3 implementation plan to `docs/README.md`;
- update `agent.md` so future coding agents understand the initialization protocol.

## Exit Criteria

Phase 3 is complete when:

- `agentops init --repo <repo-path>` installs the managed task-log protocol without overwriting user content;
- interactive initialization lets the user choose whether the task log is private, tracked, or unmanaged;
- non-interactive initialization defaults to a private session log;
- simultaneous `CLAUDE.md` and `AGENTS.md` files both receive the managed block;
- repositories without either constraint file receive `rule.md`;
- repeated initialization is idempotent;
- task reports can be parsed into bounded `SessionTrace` evidence;
- git, diff, CI, shell-output, and supported test evidence are represented by stable deterministic models;
- all existing and new tests pass;
- Phase 4 can consume the structures without loading full chat history by default.
