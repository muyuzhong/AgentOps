# AgentOps Harness

[简体中文](README.md)

AgentOps Harness is a repository-native quality evaluation and improvement system for AI coding workflows.

Tools such as Claude Code, Codex, and Cursor can execute development tasks. AgentOps Harness focuses on the quality of that work inside real repositories. It observes the workflow, explains failure modes, and turns lessons from each task into reusable repository assets.

It helps you answer:

- Did the coding agent read the right context?
- Did the changes stay within the requested scope?
- Is there enough verification evidence?
- Is a long conversation starting to degrade?
- Which rules belong in `CLAUDE.md` or `AGENTS.md`?
- Which recurring lessons should become skills, hooks, test commands, or workflow guidance?

## How it works: declaration vs ground truth

AgentOps does not simply restate what an agent claims to have done. It reconciles the agent's claims against what actually happened:

- **Declaration**: the agent's own session log, namely what it says it did, changed, and verified. An agent can fabricate this.
- **Ground truth**: git diff, command exit codes, test results. An agent cannot fabricate these.

The gap between the two is the core diagnostic signal. If the log says "only touched the login logic" but the diff shows 8 files across 3 modules, that is both scope drift and a failure of the agent's self-awareness.

## Features

Available today:

- **Repository readiness scanning**: Identify project structure, test commands, CI configuration (including validation commands), and agent instruction files, then emit a readiness score with actionable suggestions.
- **Repository initialization**: Install the session protocol and write a managed instruction block into `CLAUDE.md` / `AGENTS.md` so agents record their work in a known format.
- **Session evaluation (scope dimension)**: Reconcile the most recent task report's declaration against git truth, emit a deterministic scope-discipline score with evidence-backed findings and actionable recommendations, and append each eval to `eval-history.jsonl`. The intent-judgment LLM seam is in place and defaults to a deterministic `needs_review`.
- **Workflow tracing**: Record deterministic scan and eval steps and failures for inspection.

Under development:

- **More evaluation dimensions**: Add context-quality and verification-sufficiency on top of scope/boundary.
- **LLM-backed intent verdict**: Fill the existing injectable interface with an LLM judge that decides whether a gap falls within the task's intent.
- **Actionable diagnosis**: Detect missing context, scope drift, insufficient verification, repeated failures, and task expansion.
- **Repository-level improvements**: Suggest updates to `CLAUDE.md`, `AGENTS.md`, skills, hooks, verification commands, and context-management practices.

## Installation

AgentOps Harness requires Python 3.11 or newer.

```shell
git clone https://github.com/muyuzhong/AgentOps.git
cd AgentOps
python -m pip install -e .
```

## Usage

The project is in early development. You can inspect the CLI, initialize a repository's session protocol, and scan a repository for AI coding readiness:

```shell
agentops --help
agentops --version
```

### Initialize a repository

`agentops init` is an explicit write operation. It writes `.agentops/session-protocol.md` and `.agentops/agentops-session.md`, and appends a managed protocol block to an existing `CLAUDE.md` or `AGENTS.md`. If neither exists, it creates `rule.md`.

```shell
agentops init --repo <repo-path>

# Choose a session-log policy: private (default), tracked, or unmanaged
agentops init --repo <repo-path> --session-log-policy <private|tracked|unmanaged>
```

### Scan a repository

```shell
# Scan a repository for AI coding readiness
agentops scan --repo <repo-path>

# Artifacts default to .agentops/ in the current directory; choose another with --output
agentops scan --repo <repo-path> --output <output-path>
```

### Evaluate a session

`agentops eval` evaluates the most recent task report: it reconciles the declaration against git truth and emits a deterministic scope-discipline score, evidence-backed findings, actionable recommendations, and intent verdicts, then appends this eval to `eval-history.jsonl`. It is read-only with respect to the target repository and only writes artifacts under `--output`.

```shell
# Evaluate the most recent task report (declaration vs working tree relative to HEAD)
agentops eval --repo <repo-path>

# --session defaults to <repo>/.agentops/agentops-session.md; --diff-base defaults to HEAD (any git ref works)
agentops eval --repo <repo-path> --session <session.md> --diff-base <ref> --output <output-path>
```

The intent-judgment LLM seam is in place but the default path calls no model: a deterministic judge marks every `intent_alignment` as `needs_review`, with no API key or network. A later release fills the same interface with an LLM judge.

## Output

AgentOps Harness writes local analysis artifacts to `.agentops/`:

```text
.agentops/
  session-protocol.md      # session protocol written by init
  agentops-session.md      # where the agent appends its structured work log
  agentops-report.md       # readiness report written by scan
  agentops-score.json
  agentops-trace.json
```

The `agentops-report.md` produced by `agentops scan` is a developer-facing, human-readable report. Every deduction carries evidence and an actionable fix, not just a bare score:

```markdown
# AgentOps Repository Readiness Report

Score: 60/100

## Findings

- **missing_agent_instructions** (warning): Repository-specific agent
  instructions are missing. Evidence: `AGENTS.md`, `CLAUDE.md`
- **missing_ci_config** (warning): A common CI configuration was not
  detected. Evidence: `.github/workflows`, `.gitlab-ci.yml`

## Recommendations

- **Add agent instructions**: Add AGENTS.md or CLAUDE.md with boundaries
  and verification commands.
- **Add continuous integration checks**: Add CI configuration that runs
  the repository verification commands.
```

`agentops-trace.json` records workflow steps and failures so you can inspect how a scan completed.

`agentops eval` writes a set of evaluation artifacts under `--output`:

```text
<output>/
  agentops-report.md      # eval report: declared vs changed, findings, score, recommendations, intent verdicts
  agentops-score.json     # structured EvalResult
  agentops-trace.json     # eval workflow trace
  eval-history.jsonl      # one appended line per eval (timestamped) for trend analysis
```

Future releases will add:

```text
  suggested-claude-md.md
  suggested-agents-md.md
  skill-candidates.md
```

| File | Purpose |
| --- | --- |
| `session-protocol.md` | Fixed protocol describing how an agent records its work log |
| `agentops-session.md` | Bounded task log the agent appends to under the protocol |
| `agentops-report.md` | Developer-facing repository readiness or session evaluation report |
| `agentops-score.json` | Structured scores and diagnostic evidence for tool integrations |
| `agentops-trace.json` | Scan workflow steps and failure details |
| `suggested-claude-md.md` | Draft improvements for `CLAUDE.md` |
| `suggested-agents-md.md` | Draft improvements for `AGENTS.md` |
| `skill-candidates.md` | Recurring lessons that may become reusable skills |

## Project Scope

AgentOps Harness does not implement another coding agent and does not replace Claude Code, Codex, or Cursor. It adds repository-level quality evaluation, workflow diagnosis, and reusable operational guidance around those tools.

## Local Development

Install the development dependencies and run the test suite:

```shell
python -m pip install -e ".[dev]"
python -m pytest
```

The project advances deterministic-rules-first, writing a failing test before the implementation. Development conventions live in `docs/`.

## Development Status

AgentOps Harness is an early-stage open-source project, and interfaces may change. Repository readiness scanning, repository initialization, deterministic workflow tracing, and scope-dimension session evaluation (`agentops eval`, deterministic scoring plus an injectable intent seam and an accumulating `eval-history.jsonl`) work today; the LLM-backed intent verdict, more evaluation dimensions, diagnosis, and improvement-asset generation are landing phase by phase. Issues and discussions about real AI coding workflows are welcome.
