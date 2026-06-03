# Scope-Drift Spike Findings (Phase 3.5)

**Date:** 2026-06-03
**Spike:** `docs/superpowers/plans/2026-06-03-phase-3.5-eval-spike.md`
**Question:** Before designing Phase 4, answer two assumptions — (1) how far do purely deterministic rules go in evaluating session quality, using scope drift as the probe; (2) does the declaration-vs-ground-truth reconciliation chain actually work end to end.

This document is the spike's real deliverable. The throwaway runner and demo repo used to produce it are not kept.

## What was run

A real git working tree (temporary repo), reconciled through the real components:

```text
TranscriptParser(.agentops/agentops-session.md) -> tasks[-1]   # declaration
GitAnalyzer(repo).diff()                          -> DiffSummary # truth (git diff HEAD)
reconcile_scope(declaration, truth)               -> ScopeDriftReport
```

The agent's task report declared it only touched `src/auth.py`. The actual working tree also added `src/billing.py` and `tests/test_auth.py`.

Verbatim output (report JSON):

```json
{
  "declared_paths": ["src/auth.py"],
  "changed_paths": ["src/auth.py", "src/billing.py", "tests/test_auth.py"],
  "findings": [
    {"code": "undeclared_change", "evidence": ["src/billing.py"], "llm_needed": false},
    {"code": "undeclared_change", "evidence": ["tests/test_auth.py"], "llm_needed": false},
    {"code": "intent_alignment",
     "evidence": ["deterministic rules detected scope signals; judging whether they fall within the task's intent requires semantic reasoning"],
     "llm_needed": true}
  ]
}
```

## Answer 1 — how far deterministic rules go

**They reliably cover the file-set layer.** With no model and no network, the rules turned "the agent says X, the diff says Y" into concrete, reproducible signals:

- `undeclared_change` — files in the diff the declaration never mentions. This is the "declaration vs truth" gap made literal, and it is the highest-signal output: the agent claimed `auth.py`, the truth showed two more files.
- `declared_not_changed` — paths the agent named in `changes` that never appear in the diff (claim/truth mismatch).
- `cross_module_breadth` — an objective count of distinct top-level modules touched.

**The ceiling is intent.** Deterministic rules cannot tell that adding `tests/test_auth.py` is almost certainly *within* the intent of "return 401," while adding `src/billing.py` is suspicious. Both are emitted as identical `undeclared_change`. Distinguishing them is a semantic judgement — captured by the single `intent_alignment` finding with `llm_needed=true`. This is the precise boundary: **detection is deterministic; the verdict is not.**

Secondary ceilings observed:

- **Free-text path extraction is fuzzy.** "Adjust expired-token mapping" contains no path, so it cannot be reconciled. The reconciliation quality is bounded by whether the agent writes path-like tokens.
- **Basename matching is a heuristic.** It rescues "`auth.py` declared" vs "`src/auth.py` changed", but collides for two `utils.py` in different directories.
- **Renames** currently count only the new path (`previous_path` is ignored); a rename can look like a delete plus an undeclared add.
- **`GitAnalyzer.diff` is fixed to `git diff HEAD`** (working tree, tracked/staged only). Untracked files are invisible unless staged, and there is no configurable base for evaluating a finished task that spans commits.

## Answer 2 — does the reconciliation chain work

**Yes, end to end, on real git data.** `TranscriptParser` parsed a real session log, `GitAnalyzer().diff()` produced a real `DiffSummary` from `git diff HEAD`, and `reconcile_scope` correctly surfaced the two undeclared changes and deferred the intent verdict. The mechanism is sound, lightweight, deterministic, and reproducible — exactly the properties wanted as the spine of evaluation.

## Recommendation for Phase 4

1. **Keep the deterministic reconciliation as the first pass.** It is free, fast, reproducible, and high-signal. Run it before any model call.
2. **Introduce the LLM only at `intent_alignment`.** Feed it the declaration + the deterministic findings (+ relevant diff hunks) and ask for a per-finding verdict: drift vs incidental-but-justified. Do **not** let the model re-derive the file sets — determinism already did that reliably.
3. **Upgrade the task-log protocol** with an explicit `### Changed Files` section listing paths. This sharply improves declared/changed reconciliation and removes reliance on fuzzy free-text extraction — the single biggest quality lever found here.
4. **Make the diff base configurable** in the Phase 4 eval (not just `HEAD`), so a completed multi-commit task can be evaluated.
5. **Harden machine-facing output encoding.** During the run, Chinese text printed to a Windows `cp936` console mangled (display only; the JSON payload was ASCII and intact). Reminders/output consumed by hooks or automation should force UTF-8 or stay ASCII.

## Part A outcome — minimal stop-hook

`agentops check-session-log` works: it reminds (non-zero exit, stderr) when the session log has not grown since the recorded baseline, and is quiet (exit 0) when a new task report was appended. This is the declaration-chain reliability floor for everything above.

### Manual Stop-hook wiring (Task 3 deferred by design)

Auto-registration into `.claude/settings.json` was deferred: idempotent JSON managed-block merging is heavier than this spike warrants and is not what the spike validates. Wire it manually in the target repo's `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      { "hooks": [ { "type": "command", "command": "agentops check-session-log --repo ." } ] }
    ]
  }
}
```

Phase 4 can revisit auto-registration once the eval workflow justifies the JSON-merge machinery.
