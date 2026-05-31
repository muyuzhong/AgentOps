# AgentOps Harness

[简体中文](README.zh-CN.md)

AgentOps Harness is a repository-native quality evaluation and improvement system for AI coding workflows.

Tools such as Claude Code, Codex, and Cursor can execute development tasks. AgentOps Harness focuses on the quality of that work inside real repositories. It observes the workflow, explains failure modes, and turns lessons from each task into reusable repository assets.

It helps you answer:

- Did the coding agent read the right context?
- Did the changes stay within the requested scope?
- Is there enough verification evidence?
- Is a long conversation starting to degrade?
- Which rules belong in `CLAUDE.md` or `AGENTS.md`?
- Which recurring lessons should become skills, hooks, test commands, or workflow guidance?

## Features

- **Repository readiness scanning**: Identify project structure, test commands, CI configuration, and agent instruction files.
- **Workflow tracing**: Record deterministic scan steps and failures for inspection.
- **Session evaluation**: Analyze task descriptions, bounded session logs, git diffs, shell output, and test results. This capability is under development.
- **Actionable diagnosis**: Detect missing context, scope drift, insufficient verification, repeated failures, and task expansion. This capability is under development.
- **Repository-level improvements**: Suggest updates to `CLAUDE.md`, `AGENTS.md`, skills, hooks, verification commands, and context-management practices. This capability is under development.

## Installation

AgentOps Harness requires Python 3.11 or newer.

```shell
git clone https://github.com/muyuzhong/AgentOps.git
cd AgentOps
python -m pip install -e .
```

## Usage

The project is in early development. The current CLI can report its version and scan a repository for AI coding readiness:

```shell
agentops --help
agentops --version

# Scan a repository for AI coding readiness
agentops scan --repo <repo-path>
```

By default, scan artifacts are written to `.agentops/` in the current directory. You can select another output directory:

```shell
agentops scan --repo <repo-path> --output <output-path>
```

Offline session evaluation and repository improvement suggestions are under development. A future release will provide:

```shell
# Evaluate one AI coding workflow
agentops eval \
  --repo <repo-path> \
  --transcript <session.md> \
  --diff <changes.diff>
```

## Output

AgentOps Harness writes local analysis artifacts to `.agentops/`:

```text
.agentops/
  agentops-report.md
  agentops-score.json
  agentops-trace.json
```

`agentops-trace.json` records workflow steps and failures so you can inspect how a scan completed.

Future releases will add:

```text
  suggested-claude-md.md
  suggested-agents-md.md
  skill-candidates.md
```

| File | Purpose |
| --- | --- |
| `agentops-report.md` | Developer-facing repository readiness or session evaluation report |
| `agentops-score.json` | Structured scores and diagnostic evidence for tool integrations |
| `agentops-trace.json` | Scan workflow steps and failure details |
| `suggested-claude-md.md` | Draft improvements for `CLAUDE.md` |
| `suggested-agents-md.md` | Draft improvements for `AGENTS.md` |
| `skill-candidates.md` | Recurring lessons that may become reusable skills |

## Project Scope

AgentOps Harness does not implement another coding agent and does not replace Claude Code, Codex, or Cursor. It adds repository-level quality evaluation, workflow diagnosis, and reusable operational guidance around those tools.

## Development Status

AgentOps Harness is an early-stage open-source project. Interfaces may change. Issues and discussions about real AI coding workflows are welcome.
