# Phase 5 Repository Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the accumulated `eval-history.jsonl` into a **deterministic, regenerable repository-memory projection**. Read every past eval and distill the four things the roadmap names — score/drift **trends**, recurring **failure modes**, evidence-backed **rule candidates**, and **skill candidates** — into `agentops-memory.md` / `agentops-memory.json` / `skill-candidates.md`. Every distilled item carries "this recurred in N/M evals" historical evidence. The memory is a pure projection of history: the same `eval-history.jsonl` produces byte-for-byte the same memory, overwritten each run. No new runtime dependency, no network, no API key.

**Basis:** This is the follow-up the Phase 4 / 4.5 plans and the roadmap point to.

- Phase 4 established the data foundation: every eval appends one line to `eval-history.jsonl` — `{timestamp, result: EvalResult.to_dict(), verdict_summary: {total, by_verdict, by_source}}` (the `verdict_summary` field arrived in Phase 4.5; pre-4.5 lines lack it and must be tolerated).
- The roadmap places Phase 5 on the `CORE <--> MEMORY` edge of the architecture and on the tutorial's chapter-6 "memory system": **沉淀仓库级经验** = 历史评测 / 失败模式 / 规则 / skill 候选.
- The moat layering doc marks Phase 5–6 as the *thick* moat (repository memory + last-mile actionable output); Phase 5 is specifically the **repository memory** layer.
- Phase 4.5 explicitly handed Phase 5 one open question: *should accumulated `drift` verdicts calibrate (move) the deterministic score?* This slice **surfaces the drift trend as read-only insight and does not move the score** (decision below).

**Decisions locked for this slice** (from planning):

- **all four features, as candidate data** — trend + failure modes + rule candidates + skill candidates are all in scope, but rules/skills are produced as *structured candidates with evidence*; turning them into final `CLAUDE.md` / `AGENTS.md` text, hooks, or workflow assets is Phase 6.
- **deterministic-only, seam shaped not filled** — all distillation is deterministic (counting, trend direction, clustering by stable `code`, ranking by frequency). A provider-agnostic `MemoryNarrator` seam is *shaped* with a deterministic default, mirroring how Phase 4 shaped `IntentJudge` before Phase 4.5 filled it. The LLM narrator (natural-language naming/summarizing of failure modes and skill candidates) is deferred to an optional Phase 5.5.
- **the verdict does not move the score** — Phase 5 reads `result.score` from history to compute a trend and reports the `drift` trend, but never recomputes or writes back any eval score. Whether drift should calibrate scoring stays deferred until the accumulated trend justifies it.
- **memory is a projection, not a new store** — memory artifacts are regenerated and overwritten each run from `eval-history.jsonl`, which stays the single source of truth. No second append-only log.
- **new standalone command** — `agentops memory`; `agentops eval` stays byte-for-byte unchanged (it does not auto-refresh memory).

**Architecture:** Phase 5 adds one new read-only pipeline, orchestrated by the same `WorkflowRunner` used by scan and eval. Nothing in the eval pipeline changes.

```text
agentops memory --repo <path>
  read_history        eval-history.jsonl  → tuple[HistoryRecord, ...]   (skip blank/legacy/malformed lines)
  → build_repo_memory (deterministic projection; narrator default = identity)
       ├─ compute_score_trend      scores + drift over time → ScoreTrend
       ├─ mine_failure_modes       cluster findings + drift verdicts by stable code → FailureMode[]
       ├─ derive_rule_candidates   recurring modes → Recommendation[]  (N/M evidence; reuse RecommendationKind)
       ├─ derive_skill_candidates  recurring modes + hot paths → SkillCandidate[]
       └─ MemoryNarrator.narrate   (deterministic default: returns the projection unchanged)
  → write_memory_artifacts  agentops-memory.md, agentops-memory.json, skill-candidates.md, agentops-trace.json
```

Core principle, unchanged: **the workflow controls the process; memory is a deterministic projection of accumulated evals.** The optional LLM narrator only enriches descriptions later — it never re-derives the structural facts (counts, codes, paths), exactly as the LLM intent judge never re-derives file sets.

**Tech Stack:** Python 3.11+, standard library (`dataclasses`, `datetime`, `json`, `pathlib`, `typing.Protocol`), `pytest`. Reuse `EvalResult`, `Finding`, `Severity`, `Recommendation`, `RecommendationKind`, `IntentVerdict` constants (`VERDICT_DRIFT`), `Artifact`, `ArtifactKind`, `WorkflowRunner`, `WorkflowStep`, `TraceWriter`. **No new third-party dependency.** Every test feeds synthetic in-memory history records or temp `eval-history.jsonl` fixtures; no test touches the network.

---

## Prerequisite

Complete and verified:

```text
docs/superpowers/plans/2026-06-05-phase-4.5-llm-intent-judge.md
```

Confirm the baseline:

```powershell
python -m pytest -v
```

Expected before Phase 5 work begins:

```text
272 passed
```

(plus 1 known `PytestCollectionWarning` for the `TestResult` dataclass).

## Scope Guard

Implement only the deterministic repository-memory projection over `eval-history.jsonl`, its artifacts, the `agentops memory` command, and the shaped (unfilled) narrator seam.

Do not add in this phase:

- **score movement / verdict-driven calibration** — memory reads `result.score` and the `drift` counts to report trends; it never recomputes, deducts, refunds, or writes back any eval score. (Deferred until the accumulated drift trend justifies it.)
- **a filled LLM narrator** — define the `MemoryNarrator` protocol and exactly one deterministic implementation. The LLM narrator (and any network/API-key path) is a later optional slice. `agentops memory` makes no LLM call.
- **final improvement assets** — no `CLAUDE.md` / `AGENTS.md` text or patches, no hook generation, no workflow templates. Phase 5 emits rule/skill *candidates* (structured, evidence-backed data); Phase 6 turns them into assets.
- a second append-only memory store (memory is a regenerated projection of `eval-history.jsonl`);
- a watcher / real-time monitoring (Phase 7);
- multi-repo or team dashboards (Studio);
- new evaluation dimensions or any change to the eval pipeline / `core/eval.py` / scoring.

`agentops memory` is read-only with respect to the target repository except for writing artifacts under the chosen `--output` directory. The default `agentops eval`, `scan`, `init`, and `check-session-log` behavior MUST remain byte-for-byte unchanged.

## User-Visible Result

After Phase 5:

```powershell
# Distill accumulated eval history into repository memory:
agentops memory --repo <repo-path>
agentops memory --repo <repo-path> --history <eval-history.jsonl> --output <dir>
```

- `--history` defaults to `<repo>/.agentops/eval-history.jsonl`; `--output` defaults to `.agentops`;
- reads every history line (tolerating blank lines and pre-4.5 lines that lack `verdict_summary`), and projects them into:

```text
<output>/
  agentops-memory.md       # human-readable memory: trend, failure modes, rule candidates, skill candidates
  agentops-memory.json     # structured RepoMemory (stable schema for Phase 6 / Studio)
  skill-candidates.md      # the skill candidates as a focused, reviewable list
  agentops-trace.json      # memory workflow trace
```

- the report shows, for each recurring failure mode, **how often it recurred (N/M evals)**, its hot paths, and when it was last seen; rule candidates and skill candidates each cite the same historical evidence;
- the command prints a one-line summary (sample count, score direction, counts of failure modes / rule candidates / skill candidates) plus the artifact paths;
- a missing or empty history (no eval has run yet) fails as a structured error: exit 1, a concise stderr line (`run agentops eval first`), no traceback;
- a repository with a single eval still produces a (thin) memory — the trend direction is `unknown` until there are at least two samples.

## Target File Structure

```text
agentops/
  core/
    memory.py                  # ScoreTrend, FailureMode, SkillCandidate, RepoMemory (+ stable to_dict)
    artifact.py                # add MEMORY_REPORT, MEMORY_JSON, SKILL_CANDIDATES kinds
  parsers/
    history.py                 # HistoryRecord + EvalHistoryReader (bounded, skips blank/legacy/bad lines)
  memory/
    __init__.py                # export build_repo_memory, MemoryNarrator, DeterministicMemoryNarrator
    trend.py                   # compute_score_trend(records) -> ScoreTrend
    failure_modes.py           # mine_failure_modes(records) -> tuple[FailureMode, ...]
    candidates.py              # derive_rule_candidates(modes), derive_skill_candidates(modes, records)
    narrator.py                # MemoryNarrator protocol + DeterministicMemoryNarrator (identity)
    aggregate.py               # build_repo_memory(records, *, repo_root, narrator) -> RepoMemory
  writers/
    memory_report.py           # write memory.md + memory.json + skill-candidates.md
  runtime/
    memory.py                  # run_memory via WorkflowRunner; MemoryRunResult, MemoryWorkflowError
  cli.py                       # add `memory` subcommand
tests/
  test_memory_models.py        # model serialization + invariants
  test_history_reader.py       # parse jsonl; skip blank/legacy/malformed; bounded
  test_memory_trend.py         # direction rule; <2 samples -> unknown; drift trend
  test_memory_failure_modes.py # clustering by code + drift verdicts; ranking; hot paths
  test_memory_candidates.py    # rule candidates (reuse Recommendation) + skill candidates with N/M evidence
  test_memory_aggregate.py     # end-to-end projection; narrator injection; determinism (same in -> same out)
  test_memory_report_writer.py # md + json + skill-candidates.md; stable ordering; overwrite (not append)
  test_memory_runtime.py       # run_memory pipeline + trace; missing/empty history -> structured error
  test_cli.py                  # `agentops memory`; defaults; structured failure; others unchanged
```

## Contracts

### Memory core models (new)

```python
# agentops/core/memory.py

@dataclass(frozen=True)
class ScoreTrend:
    """跨评测的 scope-discipline 分数与漂移走向（确定性投影）。"""
    sample_count: int                  # 参与统计的评测条数
    first_score: int | None            # 最早一次分数（无样本时 None）
    last_score: int | None             # 最近一次分数
    average_score: float | None        # 平均分（固定小数位，保证可复现）
    direction: str                     # "improving" | "worsening" | "flat" | "unknown"（<2 样本为 unknown）
    drift_verdict_total: int           # 累积 drift 裁决数（取自历史行的 verdict_summary）
    def to_dict(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class FailureMode:
    """一种跨评测反复出现的失败模式（按稳定 code 聚类）。"""
    code: str                          # undeclared_change / declared_not_changed / cross_module_breadth / confirmed_drift
    occurrence_count: int              # 出现该模式的评测次数（N/M 的 N）
    sample_count: int                  # 统计窗口内的评测总数（N/M 的 M）
    hot_paths: tuple[str, ...]         # 反复出现的证据路径/模块（频次降序、路径升序，结果有界）
    last_seen: str                     # 最近一次出现的 timestamp
    summary: str                       # 确定性模板摘要（叙述接缝可后续富化）
    def to_dict(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class SkillCandidate:
    """从反复失败模式提炼的可复用 skill 候选（候选数据，非最终 skill）。"""
    slug: str                          # 稳定 id，如 declare-changed-files-checklist
    title: str
    trigger: str                       # 何时该加载这个 skill
    rationale: str                     # 为什么（确定性模板，叙述接缝可后续富化）
    evidence: tuple[str, ...]          # 历史证据：N/M + 相关路径
    def to_dict(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class RepoMemory:
    """eval-history.jsonl 的确定性投影：趋势 + 失败模式 + 规则候选 + skill 候选。"""
    repo_root: str
    sample_count: int
    trend: ScoreTrend
    failure_modes: tuple[FailureMode, ...]
    rule_candidates: tuple[Recommendation, ...]   # 复用现有 Recommendation，不新增模型
    skill_candidates: tuple[SkillCandidate, ...]
    def to_dict(self) -> dict[str, object]: ...
```

All models are immutable dataclasses with stable, JSON-friendly `to_dict()` (tuples → lists), matching the rest of `core/`.

### Eval-history reader (new)

```python
# agentops/parsers/history.py

@dataclass(frozen=True)
class HistoryRecord:
    """eval-history.jsonl 的一行经解析后的结构化记录。"""
    timestamp: str
    result: dict[str, object]          # 原样保留 EvalResult.to_dict()，投影按需取字段
    verdict_summary: dict[str, object] # 缺失（4.5 前的旧行）时回退为空摘要 {}


class EvalHistoryReader:
    """逐行读取 append-only 的 eval-history.jsonl，确定性、有界、容错。"""
    def read(self, history_path: Path) -> tuple[HistoryRecord, ...]:
        # 跳过空行；跳过无法 json 解析或缺少必需键（result）的坏行；
        # 缺失文件交由上层 runtime 转成结构化错误。保留源顺序（即时间顺序）。
        ...
```

The reader never imports git or the network; it only parses the JSONL the eval pipeline wrote. It is deliberately tolerant so a single corrupt or legacy line cannot break the projection.

### Memory narrator seam (shaped, deterministic default only)

```python
# agentops/memory/narrator.py

@runtime_checkable
class MemoryNarrator(Protocol):
    """记忆叙述接缝：把确定性投影富化为更可读的失败模式/skill 描述。

    Phase 5 只提供确定性默认实现；LLM 叙述者留到 Phase 5.5 按同一接口填充，
    且只能改写描述字段（summary / rationale / title），绝不改动结构事实
    （code / 计数 / 路径），与 LLM 意图判官"绝不重新推导文件集合"同构。
    """
    def narrate(self, memory: RepoMemory) -> RepoMemory: ...


class DeterministicMemoryNarrator:
    """默认叙述者：直接返回确定性模板投影，不改写、不触网、不需 key。"""
    def narrate(self, memory: RepoMemory) -> RepoMemory:
        return memory
```

This mirrors `IntentJudge` + `DeterministicIntentJudge`: the seam exists and is injectable now, but the only behavior this slice is deterministic. Filling it with an LLM narrator must not change the seam's shape.

### Deterministic projection (new)

```python
# agentops/memory/aggregate.py

def build_repo_memory(
    records: tuple[HistoryRecord, ...],
    *,
    repo_root: str,
    narrator: MemoryNarrator | None = None,
) -> RepoMemory:
    """把历史记录确定性地投影为 RepoMemory；narrator 默认确定性身份实现。"""
```

Deterministic rules (all provisional thresholds are flagged as such, to be calibrated from accumulated data — same discipline as the provisional scope weights):

- **Trend** (`compute_score_trend`): collect `result.score` in source (time) order; `first_score`/`last_score`/`average_score` are direct; `direction` needs ≥2 samples (else `unknown`) and compares earliest vs latest by a fixed rule (`>` → improving, `<` → worsening, `=` → flat); `drift_verdict_total` sums `verdict_summary.by_verdict.drift` across records (0 when absent).
- **Failure modes** (`mine_failure_modes`): cluster `result.findings[].code` across records into the three stable scope codes (`undeclared_change`, `declared_not_changed`, `cross_module_breadth`); additionally derive a `confirmed_drift` mode from `result.intent_verdicts[]` where `verdict == VERDICT_DRIFT` (the highest-signal, LLM-confirmed mode). `occurrence_count` = number of evals the mode appears in; `hot_paths` = evidence paths/modules ranked by frequency then path, bounded (top 10); `last_seen` = newest timestamp; ranked by `occurrence_count` desc then `code` asc.
- **Rule candidates** (`derive_rule_candidates`): for each failure mode at or above the recurrence threshold (provisional: appears in ≥2 evals), emit one `Recommendation` reusing the existing kind mapping — `undeclared_change` → `DECLARE_CHANGED_FILES`, `declared_not_changed` → `REVIEW_DECLARED_CHANGES`, `cross_module_breadth`/`confirmed_drift` → `REVIEW_SCOPE_BOUNDARY` — with a rationale that states the N/M recurrence and the hot paths.
- **Skill candidates** (`derive_skill_candidates`): from recurring modes + hot paths, emit bounded, deterministically-slugged candidates (e.g. a changed-files declaration checklist for recurring `undeclared_change`; a `<module>` change checklist when `cross_module_breadth`/`confirmed_drift` concentrate on specific hot paths), each carrying N/M + path evidence.

Determinism is a hard requirement: the same `records` always yield an identical `RepoMemory` (stable ordering, fixed rounding, no clock/random in the projection).

### Memory artifacts (new writer)

```python
# agentops/writers/memory_report.py

class MemoryReportWriter:
    """写出仓库记忆产物：覆盖写出，绝不 append（记忆是历史的可再生投影）。"""
    def write(self, memory: RepoMemory, output_dir: Path) -> tuple[Artifact, ...]:
        # agentops-memory.md   人读：趋势 / 失败模式(含 N/M + 热点路径) / 规则候选 / skill 候选
        # agentops-memory.json 结构化：镜像 RepoMemory.to_dict()，UTF-8、sort_keys、尾随换行
        # skill-candidates.md  聚焦的 skill 候选清单（agent.md 早已列为目标产物）
        ...
```

Add `MEMORY_REPORT`, `MEMORY_JSON`, `SKILL_CANDIDATES` to `ArtifactKind`. All three files are overwritten on each run (unlike `eval-history.jsonl`, which is append-only and owned by the eval pipeline).

### Memory workflow runtime (new)

```python
# agentops/runtime/memory.py

@dataclass(frozen=True)
class MemoryRunResult:
    memory: RepoMemory
    artifacts: tuple[Artifact, ...]
    trace: WorkflowTrace


class MemoryWorkflowError(RuntimeError):
    """暴露记忆流程失败时保留下来的 workflow trace（沿用 scan/eval 语义）。"""


def run_memory(
    repo_path: Path,
    history_path: Path,
    output_dir: Path,
    *,
    narrator: MemoryNarrator | None = None,
    timestamp: datetime | None = None,
) -> MemoryRunResult:
    """编排 read_history → build_repo_memory → write_memory_artifacts。"""
```

Steps run through the same `WorkflowRunner`: `read_history` → `build_memory` → `write_memory_artifacts`, with a trace written via `TraceWriter` exactly as scan/eval do. A missing history file or zero valid records raises `MemoryWorkflowError` (structured, trace-preserving). The default narrator is `DeterministicMemoryNarrator` — no LLM, no network, no key.

### CLI wiring (new command)

- `agentops memory --repo <p> [--history <jsonl>] [--output <dir>]`; `--history` defaults to `<repo>/.agentops/eval-history.jsonl`, `--output` defaults to `.agentops`.
- A thin adapter over `run_memory`, mirroring the `eval` adapter: structured `MemoryWorkflowError` → exit 1 with a concise stderr line and the trace path (when written), no traceback; unexpected exceptions are not swallowed.
- `scan`, `init`, `check-session-log`, and `eval` parsers and behavior are untouched.

## Task 1: Memory core models

**Files:** `agentops/core/memory.py`, `agentops/core/artifact.py`, `tests/test_memory_models.py`.

- [x] Write failing tests: `ScoreTrend`, `FailureMode`, `SkillCandidate`, `RepoMemory` are frozen and serialize via `to_dict()` (tuples → lists, `None` preserved, nested `Recommendation`/`FailureMode`/`SkillCandidate` serialized); `RepoMemory.rule_candidates` holds `Recommendation`; `ArtifactKind` gains `MEMORY_REPORT` / `MEMORY_JSON` / `SKILL_CANDIDATES`.
- [x] Confirm failure, implement the dataclasses + enum additions (pure stdlib), run tests (PASS).
- [x] Commit `feat: add repository-memory core models`.

## Task 2: Eval-history reader

**Files:** `agentops/parsers/history.py`, `tests/test_history_reader.py`.

- [x] Write failing tests: `EvalHistoryReader.read` parses well-formed lines into `HistoryRecord` in source order; tolerates a pre-4.5 line with no `verdict_summary` (→ `{}`); skips blank lines and lines that fail `json.loads` or lack `result`; returns `()` for an empty file. (Missing file is handled by the runtime, not the reader.)
- [x] Confirm failure, implement the bounded, tolerant reader (no git, no network), run tests (PASS).
- [x] Commit `feat: read accumulated eval history into typed records`.

## Task 3: Deterministic trend + failure-mode mining

**Files:** `agentops/memory/__init__.py`, `agentops/memory/trend.py`, `agentops/memory/failure_modes.py`, `tests/test_memory_trend.py`, `tests/test_memory_failure_modes.py`.

- [x] Write failing tests: `compute_score_trend` returns `unknown` for <2 samples, and `improving`/`worsening`/`flat` by the fixed earliest-vs-latest rule; `average_score` uses fixed rounding; `drift_verdict_total` sums `verdict_summary` drift counts (0 when absent). `mine_failure_modes` clusters the three scope codes by occurrence across evals, derives `confirmed_drift` from `drift` verdicts, ranks by `occurrence_count` desc then `code` asc, and produces bounded, stably-ordered `hot_paths` and a correct `last_seen`.
- [x] Confirm failure, implement both deterministic functions, run tests (PASS).
- [x] Commit `feat: mine deterministic score trend and failure modes`.

## Task 4: Rule and skill candidates

**Files:** `agentops/memory/candidates.py`, `tests/test_memory_candidates.py`.

- [x] Write failing tests: `derive_rule_candidates` emits one `Recommendation` per recurring failure mode (≥ threshold) using the established kind mapping, with a rationale citing the N/M recurrence; sub-threshold modes emit nothing. `derive_skill_candidates` emits bounded, deterministically-slugged `SkillCandidate`s with N/M + path evidence; no recurrence → no candidates.
- [x] Confirm failure, implement (reuse `Recommendation`/`RecommendationKind`; provisional thresholds documented in code), run tests (PASS).
- [x] Commit `feat: derive rule and skill candidates from failure modes`.

## Task 5: Projection assembly and narrator seam

**Files:** `agentops/memory/aggregate.py`, `agentops/memory/narrator.py`, `agentops/memory/__init__.py`, `tests/test_memory_aggregate.py`.

- [x] Write failing tests: `build_repo_memory(records, repo_root=..., narrator=None)` composes trend + failure modes + rule candidates + skill candidates into a `RepoMemory`; the **same records yield an identical `RepoMemory`** (determinism); `DeterministicMemoryNarrator` is the default and returns the projection unchanged; an injected stub narrator is invoked and may rewrite only description fields (assert structural facts — codes/counts/paths — are unchanged); `MemoryNarrator` is a `runtime_checkable` `Protocol` the stub satisfies; a single-record history yields `direction="unknown"`.
- [x] Confirm failure, implement the projection + seam, export from `memory/__init__.py`, run tests (PASS).
- [x] Commit `feat: assemble the repository-memory projection behind a narrator seam`.

## Task 6: Memory artifacts writer

**Files:** `agentops/writers/memory_report.py`, `tests/test_memory_report_writer.py`.

- [x] Write failing tests: `MemoryReportWriter.write` produces `agentops-memory.md` (trend section; failure modes with N/M + hot paths + last seen; rule candidates; skill candidates — stable ordering, UTF-8), `agentops-memory.json` mirroring `RepoMemory.to_dict()` (sorted keys, trailing newline), and `skill-candidates.md`; all three are **overwritten** on a second run (not appended); an empty-but-valid memory (e.g. one sample, no recurring modes) renders cleanly.
- [x] Confirm failure, implement the writer returning the three `Artifact`s, run tests (PASS).
- [x] Commit `feat: write repository-memory report, json, and skill candidates`.

## Task 7: Memory workflow runtime and CLI

**Files:** `agentops/runtime/memory.py`, `agentops/cli.py`, `tests/test_memory_runtime.py`, `tests/test_cli.py`.

- [x] Write failing tests: `run_memory(repo, history, output)` reads history, builds memory, writes the artifacts + `agentops-trace.json`, and returns a `MemoryRunResult`; a missing history file and a zero-valid-records history each raise a structured `MemoryWorkflowError` with a preserved trace; the default narrator makes no LLM/network call. `agentops memory --repo <p>` prints the summary + artifact paths and writes the artifacts; `--history` / `--output` honored; structured failure → exit 1, concise stderr, no traceback; `scan` / `init` / `check-session-log` / `eval` unchanged.
- [x] Confirm failure, implement `run_memory` (compose via `WorkflowRunner`, reuse `TraceWriter`) and the thin CLI adapter, run tests (PASS).
- [x] Commit `feat: expose the repository-memory command`.

## Task 8: Document and verify

**Files:** `README.md`, `README.en.md`, `docs/architecture.md`, `docs/development-roadmap.md`, `docs/README.md`, `docs/project-memory.md`, `agent.md`.

- [x] Update READMEs (zh+en) with `agentops memory` usage and the four memory outputs; record in `architecture.md` the memory pipeline, the `MemoryNarrator` seam, the "deterministic projection, regenerated each run, verdict does not move the score" boundary, and the `agentops/memory/` module row; in `development-roadmap.md` mark **Phase 5 complete** and set the next step to **Phase 6 improvement assets** on top of the memory candidates (and note the still-open score-calibration question + the optional Phase 5.5 LLM narrator); refresh `project-memory.md` (files, test count, decisions, commits) and `agent.md`'s "current next step".
- [x] Run `python -m pytest -v` (all pass). Verify end-to-end against this repo: `agentops memory --repo .` reads the real `eval-history.jsonl`, writes the three memory artifacts + trace, exits 0, and leaves the tracked worktree clean (read-only except `--output`). Confirm a second run overwrites (not appends) and is byte-identical.
- [x] Commit `docs: record phase 5 repository memory`.

## Parallel Development Guidance

Start sequentially (shared contracts):

```text
memory core models (Task 1)
-> eval-history reader (Task 2)
-> trend + failure modes (Task 3) -> candidates (Task 4) -> assembly + seam (Task 5)
```

Task 1 and Task 2 are independent and can run in parallel (models vs reader). Once Tasks 1–2 fix the `RepoMemory`/`HistoryRecord` contracts, the deterministic functions (Tasks 3–4) can be developed in parallel against synthetic `HistoryRecord` fixtures; Task 5 integrates them. After Task 5 stabilizes `RepoMemory`, the writer (Task 6) and the runtime+CLI (Task 7) can proceed in parallel. Keep `agentops/cli.py`, `agentops/core/artifact.py`, `agentops/memory/__init__.py`, `README.md`, and `docs/project-memory.md` edits on the integration path to avoid conflicts.

## Exit Criteria

Phase 5 is complete when:

- `agentops memory --repo <path>` projects the accumulated `eval-history.jsonl` into `agentops-memory.md`, `agentops-memory.json`, `skill-candidates.md`, and `agentops-trace.json`;
- the memory contains a score/drift **trend**, ranked **failure modes** (each with N/M recurrence, hot paths, last seen), evidence-backed **rule candidates** (reusing `Recommendation`), and **skill candidates** — all derived deterministically;
- the projection is reproducible: the same history yields a byte-identical memory, and the artifacts are overwritten (not appended) on each run;
- the `MemoryNarrator` seam exists with a deterministic default; `agentops memory` makes no LLM/network/API-key call and adds no runtime dependency;
- memory never recomputes or moves any eval score; `core/eval.py`, the scoring, and the eval/scan/init/check pipelines are unchanged;
- a missing or empty history fails as a structured error (exit 1, concise stderr, no traceback); a single-eval history still produces a thin memory with `direction="unknown"`;
- `agentops memory` is read-only with respect to the target repo except under `--output`;
- every test is deterministic and offline; `python -m pytest -v` passes.

The next step after Phase 5 is **Phase 6 improvement assets**: turn the rule/skill candidates and failure modes into actual `CLAUDE.md` / `AGENTS.md` suggestions, hook proposals, and workflow guidance. Two questions stay open for later, to be decided from the now-accumulating memory: whether `drift` trends justify letting the intent verdict calibrate the score, and whether to fill the `MemoryNarrator` seam with an optional LLM narrator (Phase 5.5).
