# Phase 4 Session Eval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the validated scope-drift reconciliation into the first real `agentops eval` — evaluate one AI coding task by reconciling the agent's declaration against git truth, emit a scored, evidence-backed report with actionable recommendations, and accumulate `eval-history.jsonl` for later trend analysis. Establish (but do not yet fill) the single LLM seam the Phase 3.5 spike identified.

**Basis:** This plan is shaped by the spike answers in `docs/superpowers/findings/2026-06-03-scope-drift-spike.md`:

- deterministic rules reliably cover the file-set layer → keep them as the first pass;
- intent is the ceiling → introduce the LLM only at `intent_alignment`, behind an interface;
- an explicit `### Changed Files` declaration is the biggest quality lever → add it to the protocol;
- a fixed `git diff HEAD` base is limiting → make the diff base configurable.

**Architecture:** Phase 4 is the first eval pipeline. It reuses the deterministic `reconcile_scope` core and runs through the existing `WorkflowRunner`, with an injectable intent judge.

```text
collect_evidence  (TranscriptParser + GitAnalyzer)  -- declaration + truth
-> reconcile_scope                                   -- deterministic file-set findings
-> judge_intent (pluggable; deterministic default)   -- verdicts; LLM seam, not filled here
-> evaluate                                          -- deterministic score + Finding + Recommendation
-> write_artifacts                                   -- report.md, score.json, eval-history.jsonl, trace.json
```

Core principle, unchanged: **the workflow controls the process; the LLM (later) only enriches the intent verdict.** The default Phase 4 path is fully deterministic and runs with no API key.

**Tech Stack:** Python 3.11+, standard library (`dataclasses`, `datetime`, `json`, `pathlib`, `typing.Protocol`), `pytest`. Reuse `TaskReport`, `SessionTrace`, `DiffSummary`, `TranscriptParser`, `GitAnalyzer`, `reconcile_scope`, `Finding`, `Recommendation`, `WorkflowRunner`, `TraceWriter`. No new third-party dependency in this phase (the LLM client lands in the follow-up that fills the seam).

---

## Prerequisite

Complete and verified:

```text
docs/superpowers/plans/2026-06-03-phase-3.5-eval-spike.md
```

Read the spike answers:

```text
docs/superpowers/findings/2026-06-03-scope-drift-spike.md
```

Confirm the baseline:

```powershell
python -m pytest -v
```

Expected before Phase 4 work begins:

```text
187 passed
```

## Scope Guard

Implement only the deterministic single-task eval pipeline and the intent-judge seam.

Do not add in this phase:

- a live LLM call or any network/API-key dependency (only the injectable seam + a deterministic default judge);
- evaluation dimensions beyond scope/boundary (context-quality and verification-sufficiency dimensions are later slices);
- multi-task or multi-session batch evaluation (evaluate the most recent task report);
- the Phase 5 memory store or trend reports (only append `eval-history.jsonl`);
- a watcher process or any real-time monitoring;
- automatic edits to application source code or to `CLAUDE.md` / `AGENTS.md`.

`agentops eval` is read-only with respect to the target repository except for writing artifacts under the chosen `--output` directory.

## User-Visible Result

After Phase 4:

```powershell
agentops eval --repo <repo-path>
agentops eval --repo <repo-path> --session <session.md> --diff-base <ref> --output <dir>
```

- `--session` defaults to `<repo>/.agentops/agentops-session.md`;
- `--diff-base` defaults to `HEAD` (working tree vs HEAD); any git ref is accepted;
- evaluates the most recent task report against the diff;
- prints the scope-discipline score and the artifact paths;
- writes:

```text
<output>/
  agentops-report.md      # eval report: declared vs changed, findings, score, recommendations, intent verdicts
  agentops-score.json     # structured EvalResult
  agentops-trace.json     # eval workflow trace
  eval-history.jsonl      # one appended line per eval (timestamped)
```

The session protocol gains an explicit `### Changed Files` section so agents declare changed paths directly.

## Target File Structure

```text
agentops/
  cli.py                       # add `eval`
  core/
    eval.py                    # EvalResult, IntentVerdict
    session.py                 # TaskReport gains changed_files
  initializers/
    repo.py                    # session-protocol.md gains ### Changed Files
  parsers/
    transcript.py              # parse ### Changed Files
  analyzers/
    git.py                     # diff(base=...)
  evaluators/
    scope_drift.py             # prefer changed_files when present
    session_eval.py            # deterministic score + Finding/Recommendation
  judges/
    __init__.py
    intent.py                  # IntentJudge protocol + DeterministicIntentJudge
  writers/
    eval_report.py             # markdown + json + history append
  runtime/
    eval.py                    # run_eval via WorkflowRunner
tests/
  test_eval_models.py
  test_session_eval.py
  test_intent_judge.py
  test_eval_report_writer.py
  test_eval_runtime.py
  test_cli.py                  # eval command
  test_transcript_parser.py    # changed_files
  test_git_analyzer.py         # diff base
```

## Contracts

### Declaration upgrade

```python
@dataclass(frozen=True)
class TaskReport:
    ...
    changed_files: tuple[str, ...] = ()   # explicit declared paths (new)
```

`### Changed Files` is an optional list section. `reconcile_scope` uses `changed_files` as the declared-change set when present, falling back to the existing path extraction from `changes` otherwise.

### Intent seam

```python
class IntentVerdict:
    finding_code: str
    evidence: tuple[str, ...]
    verdict: str        # "within_intent" | "drift" | "needs_review"
    rationale: str
    source: str         # "deterministic" | "llm"


class IntentJudge(Protocol):
    def judge(
        self, task_report: TaskReport, report: ScopeDriftReport
    ) -> tuple[IntentVerdict, ...]: ...


class DeterministicIntentJudge:
    """默认实现：每个 intent_alignment 标为 needs_review，source=deterministic，不调用 LLM。"""
```

`run_eval(..., intent_judge: IntentJudge | None = None)` defaults to `DeterministicIntentJudge`. Tests inject a stub judge; the real LLM-backed judge is out of scope here.

### Eval result

```python
@dataclass(frozen=True)
class EvalResult:
    repo_root: Path
    task_title: str
    declared_paths: tuple[str, ...]
    changed_paths: tuple[str, ...]
    score: int                              # 0-100 deterministic scope-discipline score
    findings: tuple[Finding, ...]
    recommendations: tuple[Recommendation, ...]
    intent_verdicts: tuple[IntentVerdict, ...]

    def to_dict(self) -> dict[str, object]: ...
```

Scoring is deterministic, starts at 100, and deducts per drift finding (provisional weights, every deduction carries evidence + a recommendation, same discipline as readiness; weights are explicitly provisional pending real data). `score` floors at 0.

## Task 1: Declare changed files explicitly

**Files:** `agentops/core/session.py`, `agentops/parsers/transcript.py`, `agentops/initializers/repo.py`, `agentops/evaluators/scope_drift.py`, and their tests.

- [ ] Write failing tests: `TaskReport.changed_files` serializes; `TranscriptParser` parses an optional `### Changed Files` list; `reconcile_scope` prefers `changed_files` over free-text extraction; `session-protocol.md` template includes the new section.
- [ ] Confirm failure, implement, run tests (PASS).
- [ ] Commit `feat: declare changed files in the task-log protocol`.

## Task 2: Configurable diff base

**Files:** `agentops/analyzers/git.py`, `tests/test_git_analyzer.py`.

- [ ] Write failing tests: `GitAnalyzer().diff(repo, base="<ref>")` runs `git diff ... <ref>`; default stays `HEAD`; invalid ref surfaces `GitAnalysisError`.
- [ ] Confirm failure, implement (keep `shell=False`, controlled args), run tests (PASS).
- [ ] Commit `feat: support a configurable git diff base`.

## Task 3: Eval models, scoring, and intent seam

**Files:** `agentops/core/eval.py`, `agentops/evaluators/session_eval.py`, `agentops/judges/{__init__,intent}.py`, tests.

- [ ] Write failing tests: `EvalResult`/`IntentVerdict` serialize stably; deterministic score deducts per drift finding with evidence + recommendation; aligned task scores 100 with no findings; `DeterministicIntentJudge` marks `intent_alignment` as `needs_review` / `source="deterministic"` and never calls a model.
- [ ] Confirm failure, implement, run tests (PASS).
- [ ] Commit `feat: deterministic session-eval scoring and intent seam`.

## Task 4: Eval pipeline through the workflow runtime

**Files:** `agentops/runtime/eval.py`, `tests/test_eval_runtime.py`.

- [ ] Write failing tests: `run_eval(repo, session, output, diff_base, intent_judge)` collects declaration (most recent task) + truth, reconciles, judges, and returns an `EvalResult`; a missing session or empty log fails as a structured error; the eval workflow records a trace with the same event/failure semantics as scan.
- [ ] Confirm failure, implement by composing existing components through `WorkflowRunner`, run tests (PASS).
- [ ] Commit `feat: run the session-eval workflow`.

## Task 5: Eval artifacts and history

**Files:** `agentops/writers/eval_report.py`, `tests/test_eval_report_writer.py`.

- [ ] Write failing tests: markdown report shows task, declared vs changed paths, findings, score, recommendations, intent verdicts; JSON mirrors `EvalResult.to_dict()`; `eval-history.jsonl` appends exactly one line per eval with a passed-in timestamp, preserving prior lines.
- [ ] Confirm failure, implement (UTF-8, stable ordering, append-only history), run tests (PASS).
- [ ] Commit `feat: write session-eval report, score, and history`.

## Task 6: Expose `agentops eval`

**Files:** `agentops/cli.py`, `tests/test_cli.py`.

- [ ] Write failing tests: `agentops eval --repo <p>` writes artifacts and prints the score; `--session` / `--diff-base` / `--output` honored; structured failure (missing repo/session) returns exit 1 with a concise stderr message and no traceback; unexpected errors are not hidden. Keep `scan`, `init`, `check-session-log` unchanged.
- [ ] Confirm failure, implement a thin adapter over `run_eval`, run tests (PASS).
- [ ] Commit `feat: expose the session-eval command`.

## Task 7: Document and verify

**Files:** `README.md`, `README.en.md`, `docs/architecture.md`, `docs/development-roadmap.md`, `docs/README.md`, `docs/project-memory.md`, `agent.md`.

- [ ] Update README (zh+en) with `agentops eval` usage; record the eval pipeline, intent seam, and the "deterministic default, LLM-as-next-step" boundary in architecture; mark Phase 4 complete in the roadmap and set the next step to **fill the LLM intent seam**; refresh project-memory (files, test count, decisions, commits).
- [ ] Run `python -m pytest -v` (all pass); run `agentops eval` against a real `.agentops/agentops-session.md` + working tree and confirm artifacts + read-only behavior + clean tracked worktree.
- [ ] Commit `docs: record phase four session eval`.

## Parallel Development Guidance

Start sequentially (shared contracts):

```text
changed_files protocol (Task 1)
-> eval models + scoring + intent seam (Task 3)
```

Task 2 (diff base) is independent and can run in parallel with Task 1. After Task 3 stabilizes the `EvalResult` contract, the writer (Task 5) and runtime (Task 4) can proceed in parallel; the CLI (Task 6) integrates last. Keep `agentops/cli.py`, `agentops/core/__init__.py`, `README.md`, and `docs/project-memory.md` edits on the integration path to avoid conflicts.

## Exit Criteria

Phase 4 is complete when:

- `agentops eval --repo <path>` evaluates the most recent task report against the diff and writes `agentops-report.md`, `agentops-score.json`, `agentops-trace.json`, and an appended `eval-history.jsonl`;
- the protocol and parser support an explicit `### Changed Files` declaration, and `reconcile_scope` prefers it;
- the diff base is configurable, defaulting to `HEAD`;
- every score deduction carries evidence and an actionable recommendation;
- the intent judge is injectable, defaults to a deterministic `needs_review`, and the default path makes no LLM/network call;
- existing `scan` / `init` / `check-session-log` behavior is unchanged and read-only with respect to target sources;
- `python -m pytest -v` passes.

The next step after Phase 4 is to fill the intent seam with an LLM-backed `IntentJudge` (behind the same interface, stubbed in tests), then plan Phase 5 repository memory on top of the accumulated `eval-history.jsonl`.
