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
- **Session evaluation (scope dimension)**: Reconcile the most recent task report's declaration against git truth, emit a deterministic scope-discipline score with evidence-backed findings and actionable recommendations, and append each eval to `eval-history.jsonl`.
- **Intent verdict (optional LLM)**: `--intent-judge llm` gives each deterministic drift finding a per-finding verdict — within the task's intent or real drift (`within_intent` / `drift`). The default stays offline and deterministic (`needs_review`), and any failure degrades automatically. The verdict only enriches the report; it never moves the deterministic score.
- **Repository memory (deterministic projection)**: `agentops memory` distills the accumulated `eval-history.jsonl` into repository memory — a score/drift trend, recurring failure modes (each carrying "recurred in N/M evals" evidence), evidence-backed rule candidates, and skill candidates. The memory is a regenerable projection of history: the same history yields a byte-identical memory, offline and deterministic, and it never moves any eval score.
- **Improvement assets (deterministic projection)**: `agentops suggest` projects repository memory plus the repo's current instruction files into ready-to-adopt assets — an `agentops:repo-rules` managed block for `CLAUDE.md` / `AGENTS.md` (additions) with deterministic trim diagnostics (subtractions: over-budget length, verbatim README duplication), hook proposals mapping recurring failure modes to existing `agentops` commands (with a `settings.json` snippet), plus workflow guidance and skill scaffolds. It is read-only with respect to the target repo (it never rewrites the instruction files), offline, regenerable, and never moves the score.
- **Workflow tracing**: Record deterministic scan and eval steps and failures for inspection.

Under development:

- **More evaluation dimensions**: Add context-quality and verification-sufficiency on top of scope/boundary.
- **Actionable diagnosis**: Detect missing context, scope drift, insufficient verification, repeated failures, and task expansion.
- **Real-time supervision**: Observe the AI coding process, surface risks, and suggest interventions (Phase 7).

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

The intent-judgment LLM seam is in place but the default path calls no model: a deterministic judge marks every `intent_alignment` as `needs_review`, with no API key or network.

### Optional: judge intent with an LLM

By default `agentops eval` is fully offline and deterministic and needs no API key. Adding `--intent-judge llm` sends each deterministic drift finding to a model for a per-finding "within intent vs real drift" verdict:

```shell
# Set the API key for your OpenAI-compatible endpoint (default endpoint is mimo;
# override with --intent-base-url / AGENTOPS_LLM_BASE_URL)
export AGENTOPS_LLM_API_KEY="<your-key>"            # bash
agentops eval --repo <repo-path> --intent-judge llm --intent-model mimo-v2.5-pro
```

- `--intent-judge` defaults to `deterministic` (the Phase 4 behavior); set it to `llm` to enable the model.
- `--intent-model` selects the model id; `--intent-base-url` / `AGENTOPS_LLM_BASE_URL` override the endpoint; the key is read from the `AGENTOPS_LLM_API_KEY` environment variable.
- If the key or model is missing, the network fails, or the response is unparsable, the judge degrades to the deterministic `needs_review`, the eval still exits 0, and one fallback notice is printed to stderr.
- LLM verdicts only enrich the report (grouped by `drift` / `within_intent` / `needs_review` and labeled by source); they **do not** move the deterministic scope score.
- The adapter calls the OpenAI-compatible endpoint over standard-library HTTP and adds no new dependency (`import agentops` needs no third-party SDK).

### Distill repository memory

`agentops memory` projects the accumulated `eval-history.jsonl` into repository memory deterministically: it reads every history line (tolerating blank lines, corrupt lines, and older lines that predate the verdict summary), distills a score/drift **trend**, recurring **failure modes**, evidence-backed **rule candidates**, and **skill candidates**, then overwrites the memory artifacts. It is read-only with respect to the target repository and only writes under `--output`; it is offline and deterministic, calls no model, needs no API key, and adds no dependency.

```shell
# Distill the accumulated eval history into repository memory
agentops memory --repo <repo-path>

# --history defaults to <repo>/.agentops/eval-history.jsonl; --output defaults to .agentops
agentops memory --repo <repo-path> --history <eval-history.jsonl> --output <output-path>
```

- Each recurring failure mode is annotated with "recurred in N/M evals", its hot paths, and when it was last seen; rule and skill candidates cite the same historical evidence.
- The memory is a **regenerable projection**: the same history yields a byte-identical memory, and each run overwrites (never appends); `eval-history.jsonl` stays the single source of truth.
- The memory only **reads** eval scores to compute a trend; it never recomputes or writes back any score. Whether the drift trend should calibrate the score is deferred until the accumulated data justifies it.
- If no eval has run yet (history missing or empty), the command exits with a structured error (exit 1, a hint to run `agentops eval` first, no traceback).

### Generate improvement assets

`agentops suggest` re-projects the accumulated `eval-history.jsonl` into repository memory, reads the repo's current `CLAUDE.md` / `AGENTS.md` / `README.md` read-only, and projects memory plus those instruction files into **ready-to-adopt improvement assets** deterministically, overwriting them each run. It is read-only with respect to the target repository and only writes under `--output`; it is offline and deterministic, calls no model, needs no API key, and adds no dependency.

```shell
# Project accumulated memory into adoptable improvement assets
agentops suggest --repo <repo-path>

# --history defaults to <repo>/.agentops/eval-history.jsonl; --output defaults to .agentops
agentops suggest --repo <repo-path> --history <eval-history.jsonl> --output <output-path>
```

- **`CLAUDE.md` / `AGENTS.md` suggestions**: a paste-ready `agentops:repo-rules` managed block (one bullet per recurring rule, each citing its N/M recurrence — additions), deterministic trim diagnostics (subtractions: over the ~200-line budget, verbatim README duplication), and a "create this file" note when the target is missing. These `repo-rules` markers are intentionally distinct from `init`'s `session-protocol` markers, so both blocks coexist in one file.
- **Hook proposals**: for each failure mode at or above the recurrence threshold, a Claude Code hook (event + an existing `agentops` command) with a copy-paste `settings.json` snippet; modes mapping to the same command collapse into one proposal.
- **Workflow guidance**: a one-line trend summary, the recommended `eval → memory → suggest` cadence, and skill scaffolds derived from the skill candidates.
- **Suggest, don't rewrite**: `agentops suggest` writes *review drafts* under `--output` only; it is read-only with respect to the target repo's `CLAUDE.md` / `AGENTS.md` / `README.md` and never edits them in place. Adoption stays the user's decision.
- The assets are a **regenerable projection** of memory plus the instruction files: the same inputs yield byte-identical assets, overwritten each run (never appended). A missing or empty history exits with the same structured error (hint to run `agentops eval` first).

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

`agentops memory` projects the accumulated `eval-history.jsonl` above into a set of memory artifacts (overwritten each run):

```text
<output>/
  agentops-memory.md       # human-readable memory: trend, failure modes (with N/M + hot paths), rule candidates, skill candidates
  agentops-memory.json     # structured RepoMemory (for later phases / tool integrations)
  skill-candidates.md      # focused, reviewable list of skill candidates
  agentops-trace.json      # memory workflow trace
```

`agentops suggest` projects accumulated memory plus the current instruction files into a set of adoptable improvement assets (overwritten each run):

```text
<output>/
  suggested-claude-md.md     # CLAUDE.md: adoptable repo-rules block (additions) + trim diagnostics (subtractions) + missing-file note
  suggested-agents-md.md     # the same, targeting AGENTS.md
  suggested-hooks.md         # one hook proposal per recurring failure mode + settings.json snippets + workflow guidance + skill scaffolds
  agentops-suggestions.json  # structured ImprovementAssets (for Studio / Phase 7)
  agentops-trace.json        # suggest workflow trace
```

| File | Purpose |
| --- | --- |
| `session-protocol.md` | Fixed protocol describing how an agent records its work log |
| `agentops-session.md` | Bounded task log the agent appends to under the protocol |
| `agentops-report.md` | Developer-facing repository readiness or session evaluation report |
| `agentops-score.json` | Structured scores and diagnostic evidence for tool integrations |
| `agentops-trace.json` | Scan / eval / memory workflow steps and failure details |
| `eval-history.jsonl` | Append-only history (one line per eval), the sole data source for memory |
| `agentops-memory.md` | Repository memory report: trend, failure modes, rule candidates, skill candidates |
| `agentops-memory.json` | Structured repository memory for Phase 6 / tool integrations |
| `skill-candidates.md` | Recurring lessons that may become reusable skills |
| `suggested-claude-md.md` | Draft improvements for `CLAUDE.md`: adoptable repo-rules block (additions) + trim diagnostics (subtractions) + missing-file note |
| `suggested-agents-md.md` | Draft improvements for `AGENTS.md` (same shape) |
| `suggested-hooks.md` | Hook proposals + `settings.json` snippets + workflow guidance + skill scaffolds |
| `agentops-suggestions.json` | Structured ImprovementAssets for Studio / Phase 7 |

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

AgentOps Harness is an early-stage open-source project, and interfaces may change. Repository readiness scanning, repository initialization, deterministic workflow tracing, and scope-dimension session evaluation (`agentops eval`, deterministic scoring plus an accumulating `eval-history.jsonl`) work today, along with an optional LLM intent verdict (`--intent-judge llm`, a `within_intent` / `drift` verdict per drift finding that degrades to the deterministic `needs_review` on any failure and never moves the score), a deterministic repository-memory projection (`agentops memory`, distilling the accumulated history into a trend, failure modes, rule candidates, and skill candidates — offline, regenerable, and never moving the score), and a deterministic improvement-asset projection (`agentops suggest`, turning memory plus the current instruction files into `CLAUDE.md` / `AGENTS.md` managed blocks plus trim diagnostics, hook proposals, and workflow guidance — read-only with respect to the target repo, offline, regenerable, and never moving the score); more evaluation dimensions, diagnosis, and real-time supervision are landing phase by phase. Issues and discussions about real AI coding workflows are welcome.
