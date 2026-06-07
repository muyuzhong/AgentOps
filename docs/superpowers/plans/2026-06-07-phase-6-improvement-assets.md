# Phase 6 Improvement Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Turn the Phase 5 repository memory into **ready-to-adopt improvement assets** that a human (or a coding agent) can review and apply. Read the accumulated memory — recurring **failure modes**, evidence-backed **rule candidates** (`Recommendation`), reusable **skill candidates**, and the score/drift **trend** — and project it, deterministically, into the three asset families the roadmap names:

- **`CLAUDE.md` / `AGENTS.md` suggestions** — a ready-to-paste AgentOps-managed *rules block* distilled from recurring failure modes (加法), plus deterministic *trim* diagnostics on any existing instruction file (减法: over-budget length, content duplicated from the README), plus a "this file is missing — create it" note when it is absent;
- **hook proposals** — for each recurring failure mode, a concrete Claude Code hook (event + the existing `agentops` command that would catch it) with a copy-paste `settings.json` snippet;
- **workflow guidance** — a trend-aware one-line summary, a recommended `eval → memory → suggest` cadence, and skill scaffolds derived from the skill candidates.

Every asset carries the same "this recurred in N/M evals" historical evidence Phase 5 attached to its candidates. The assets are a pure projection of memory + the repo's current instruction files: the same inputs produce byte-for-byte the same assets, overwritten each run. No new runtime dependency, no network, no API key.

**Basis:** This is the slice Phase 5 and the roadmap point to.

- The roadmap places Phase 6 as **改进资产 / Improvement Assets** — `CLAUDE.md`、`AGENTS.md`、hook 和流程建议 — built **on top of** the Phase 5 memory candidates (`docs/development-roadmap.md`).
- `agent.md` already names the orchestration verb (`scan / eval / suggest / report`) and the target outputs (`suggested-claude-md.md`, `suggested-agents-md.md`); `architecture.md` lists the same `suggest` verb in the access layer.
- `architecture.md` 建议引擎设计 fixes the core principle: **AgentOps 负责诊断，不负责执行改写** — `CLAUDE.md` optimization is 加法 *and* 减法 (keep it under ~200 lines), the engine outputs 缺什么 / 多什么 / 哪些该精简 plus adoptable managed text, and the actual rewrite stays the user's decision.
- Phase 5 explicitly handed Phase 6 the candidate data and left two questions deferred (does `drift` trend calibrate the score? do we fill the `MemoryNarrator` seam with an LLM?). **Phase 6 resolves neither** — see Scope Guard.

**Decisions locked for this slice** (from the roadmap, `agent.md`, and Phase 5):

- **suggest, don't rewrite** — `agentops suggest` writes *review drafts* under `--output` (`suggested-claude-md.md`, …). It is **read-only with respect to the target repo's `CLAUDE.md` / `AGENTS.md` / `README.md`** and never edits them in place. This honors `agent.md`'s "不自动修改用户仓库" while still delivering "可直接采纳的文本": the drafts contain a fully-rendered AgentOps-managed block the user can paste. An opt-in in-place `--write` (reusing `initializers/repo.py`'s managed-block machinery) is explicitly deferred.
- **distinct managed-block markers** — the suggested rules block uses `<!-- agentops:repo-rules:start -->` / `…:end`, *distinct* from `init`'s `agentops:session-protocol` markers, so adopting Phase 6 rules never collides with the Phase 3 protocol block. Both blocks coexist in one `CLAUDE.md`.
- **deterministic-only, seam shaped not filled** — all projection is deterministic (reuse Phase 5's distilled candidates; map codes → hooks; count lines; substring-match the README). A provider-agnostic `AssetNarrator` seam is *shaped* with a deterministic identity default, mirroring how Phase 4 shaped `IntentJudge` and Phase 5 shaped `MemoryNarrator`. The LLM narrator — the natural home for semantic 减法 judgment ("these lines are tutorial bloat") and prose polish — is deferred to a later optional slice. `agentops suggest` makes **no** LLM call.
- **reuse models, add only wrappers** — additions reuse `Recommendation` (the rule candidates already *are* `Recommendation`s); subtraction diagnostics reuse `Finding` / `Severity`; skill scaffolds reuse `SkillCandidate`. Phase 6 adds only three small wrapper models (`InstructionSuggestion`, `HookProposal`, `ImprovementAssets`) — no parallel candidate hierarchy.
- **assets are a projection, not a new store** — assets are regenerated and overwritten each run from `eval-history.jsonl` + the repo's current instruction files. There is no second persisted store; memory stays the single distilled source and `eval-history.jsonl` stays the single raw source.
- **re-project memory, don't depend on stale artifacts** — `suggest` rebuilds `RepoMemory` from history (reusing Phase 5's `read_history` + `build_repo_memory`) rather than reading a possibly-stale `agentops-memory.json`. Determinism and single-source-of-truth are preserved.
- **new standalone command** — `agentops suggest`; `scan` / `eval` / `memory` / `init` / `check-session-log` stay byte-for-byte unchanged.

**Architecture:** Phase 6 adds one new read-only pipeline, orchestrated by the same `WorkflowRunner` used by scan / eval / memory. Its first two steps are exactly Phase 5's memory steps; nothing in the eval or memory pipeline changes.

```text
agentops suggest --repo <path>
  read_history          eval-history.jsonl  → tuple[HistoryRecord, ...]   (reuse Phase 5 reader; skip blank/legacy/bad lines)
  → build_repo_memory   (reuse Phase 5 deterministic projection → RepoMemory)
  → read_instructions   read CLAUDE.md / AGENTS.md / README.md (read-only) → dict[str, str | None]
  → build_improvement_assets (deterministic projection; narrator default = identity)
       ├─ derive_instruction_suggestions  rule candidates → adoptable repo-rules block (加法);
       │                                   existing file length + README duplication → trim diagnostics (减法)
       ├─ derive_hook_proposals            recurring failure modes → Stop-hook proposals + settings.json snippet
       ├─ (trend + skill candidates)       trend_summary + recommended cadence + skill scaffolds
       └─ AssetNarrator.narrate            (deterministic default: returns the projection unchanged)
  → write_improvement_artifacts  suggested-claude-md.md, suggested-agents-md.md, suggested-hooks.md,
                                  agentops-suggestions.json, agentops-trace.json
```

Core principle, unchanged: **the workflow controls the process; assets are a deterministic projection of accumulated memory.** The optional LLM narrator only enriches descriptions later — it never re-derives the structural facts (rule kinds, hook commands, counts, paths), exactly as the LLM intent judge never re-derives file sets and the (future) memory narrator never re-derives codes.

**Tech Stack:** Python 3.11+, standard library (`dataclasses`, `datetime`, `json`, `pathlib`, `re`, `typing.Protocol`), `pytest`. Reuse `Recommendation`, `RecommendationKind`, `Finding`, `Severity`, `RepoMemory`, `FailureMode`, `SkillCandidate`, `ScoreTrend`, `Artifact`, `ArtifactKind`, `EvalHistoryReader`, `build_repo_memory`, `WorkflowRunner`, `WorkflowStep`, `TraceWriter`, and the `RECURRENCE_THRESHOLD` / `CONFIRMED_DRIFT` constants. **No new third-party dependency.** Every test feeds synthetic in-memory `RepoMemory` / instruction strings or temp fixtures; no test touches the network.

---

## Prerequisite

Complete and verified:

```text
docs/superpowers/plans/2026-06-06-phase-5-repository-memory.md
```

Confirm the baseline:

```powershell
python -m pytest -v
```

Expected before Phase 6 work begins:

```text
337 passed
```

(plus 1 known `PytestCollectionWarning` for the `TestResult` dataclass).

## Scope Guard

Implement only the deterministic improvement-asset projection over `RepoMemory` + the repo's current instruction files, its artifacts, the `agentops suggest` command, and the shaped (unfilled) `AssetNarrator` seam.

Do not add in this phase:

- **in-place edits to the user's repo** — `agentops suggest` writes only under `--output`. It never modifies `CLAUDE.md`, `AGENTS.md`, `README.md`, `rule.md`, or `settings.json` in the target repo. The opt-in `--write` path (reusing `initializers/repo.py`) is a later slice.
- **a filled LLM narrator** — define the `AssetNarrator` protocol and exactly one deterministic identity implementation. No network / API-key path. Semantic 减法 (deciding which existing instruction lines are tutorial bloat vs. project constraint) and prose polish stay deterministic-or-deferred.
- **score movement / verdict-driven calibration** — assets read `trend` and failure counts to *describe* them; they never recompute, deduct, or write back any eval score. (Still deferred from Phase 5, until the accumulated drift trend justifies it.)
- **a second persisted store** — assets are a regenerated projection of `eval-history.jsonl` + current instruction files; no new append-only log, no caching layer.
- **a general CLAUDE.md linter / rewriter** — subtraction diagnostics are limited to deterministic, defensible signals (line-count budget, verbatim README duplication). No grammar/style rules, no AST of Markdown, no auto-trimming.
- a watcher / real-time monitoring (Phase 7);
- multi-repo or team dashboards (Studio);
- new evaluation dimensions or any change to the eval / memory pipelines, `core/eval.py`, `core/memory.py`, scoring, or the `memory` artifacts.

`agentops suggest` is read-only with respect to the target repository except for writing artifacts under the chosen `--output` directory. The default `agentops scan`, `eval`, `memory`, `init`, and `check-session-log` behavior MUST remain byte-for-byte unchanged.

## User-Visible Result

After Phase 6:

```powershell
# Project accumulated memory into adoptable improvement assets:
agentops suggest --repo <repo-path>
agentops suggest --repo <repo-path> --history <eval-history.jsonl> --output <dir>
```

- `--history` defaults to `<repo>/.agentops/eval-history.jsonl`; `--output` defaults to `.agentops`;
- re-projects the history into `RepoMemory` (tolerating blank / pre-4.5 / malformed lines exactly as `memory` does), reads the repo's current `CLAUDE.md` / `AGENTS.md` / `README.md` read-only, and writes:

```text
<output>/
  suggested-claude-md.md     # for CLAUDE.md: adoptable repo-rules block (加法) + trim diagnostics (减法) + missing-file note
  suggested-agents-md.md     # the same, targeting AGENTS.md
  suggested-hooks.md         # one Stop-hook proposal per recurring failure mode + settings.json snippets + workflow guidance + skill scaffolds
  agentops-suggestions.json  # structured ImprovementAssets (stable schema for Studio / Phase 7)
  agentops-trace.json        # suggest workflow trace
```

- each instruction suggestion shows **what to add** (a ready-to-paste `agentops:repo-rules` managed block, one bullet per recurring rule candidate, each citing its N/M recurrence), **what to trim** (deterministic findings: the file exceeds the line budget; a paragraph duplicates the README), and **whether the file is missing** (then: additive-only, with a "create this file" recommendation);
- each hook proposal names the failure mode it addresses, the hook event, the existing `agentops` command, and a copy-paste `settings.json` fragment;
- the command prints a one-line summary (sample count, trend direction, counts of instruction suggestions / hook proposals / skill candidates) plus the artifact paths;
- a missing or empty history (no eval has run yet) fails as a structured error: exit 1, a concise stderr line (`run agentops eval first`), no traceback — identical to `agentops memory`;
- a **thin** history (one eval, or no failure mode reaching the recurrence threshold) still produces clean assets: the rules block is omitted with an explicit "no recurring rules distilled yet" note, hook proposals are empty, and the instruction suggestions still carry the file-existence and size diagnostics. Determinism holds at every sample count.

## Target File Structure

```text
agentops/
  core/
    asset.py                   # InstructionSuggestion, HookProposal, ImprovementAssets (+ stable to_dict)
    artifact.py                # add SUGGESTED_CLAUDE_MD, SUGGESTED_AGENTS_MD, HOOK_PROPOSALS, SUGGESTIONS_JSON kinds
  improve/
    __init__.py                # export build_improvement_assets, AssetNarrator, DeterministicAssetNarrator
    instructions.py            # derive_instruction_suggestions(memory, instructions, readme) -> tuple[InstructionSuggestion, ...]
    hooks.py                   # derive_hook_proposals(modes) -> tuple[HookProposal, ...]
    narrator.py                # AssetNarrator protocol + DeterministicAssetNarrator (identity)
    aggregate.py               # build_improvement_assets(memory, *, repo_root, instructions, readme, narrator) -> ImprovementAssets
  writers/
    improvement_report.py      # write suggested-claude-md.md + suggested-agents-md.md + suggested-hooks.md + agentops-suggestions.json
  runtime/
    improve.py                 # run_suggest via WorkflowRunner; ImproveRunResult, ImproveWorkflowError
  cli.py                       # add `suggest` subcommand
tests/
  test_asset_models.py         # model serialization + invariants
  test_improve_instructions.py # additive block from rule candidates; trim diagnostics (size, README dup); missing-file note
  test_improve_hooks.py        # code→event/command mapping; threshold gating; dedupe; settings snippet
  test_improve_aggregate.py    # end-to-end projection; narrator injection; determinism (same in -> same out); thin-memory case
  test_improvement_report_writer.py # md x3 + json; stable ordering; overwrite (not append); empty/thin assets render cleanly
  test_improve_runtime.py      # run_suggest pipeline + trace; missing/empty history -> structured error; reads instructions read-only
  test_cli.py                  # `agentops suggest`; defaults; structured failure; others unchanged
```

## Contracts

### Asset core models (new)

```python
# agentops/core/asset.py

@dataclass(frozen=True)
class InstructionSuggestion:
    """对一个指令文件（CLAUDE.md / AGENTS.md）的改进建议：加法 + 减法 + 可采纳托管块。"""
    target: str                              # "CLAUDE.md" | "AGENTS.md"
    exists: bool                             # 目标文件当前是否存在（不存在 → 纯加法 + “建议新建”）
    line_count: int | None                   # 现有文件行数（不存在时 None）
    additions: tuple[Recommendation, ...]    # 该加什么：复用规则候选；文件缺失时追加一条 ADD_CONSTRAINT_FILE
    subtractions: tuple[Finding, ...]        # 该精简什么：确定性结构诊断（超长 / 重复 README）
    managed_block: str                       # 可直接采纳的 agentops:repo-rules 托管块文本（含 marker；无规则时为空串）
    def to_dict(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class HookProposal:
    """一条 hook 提案：针对某个反复失败模式，建议装哪个 hook、跑什么 agentops 命令。"""
    slug: str                  # 稳定 id，如 declare-changed-files-stop-hook
    failure_codes: tuple[str, ...]  # 触发该提案的失败模式 code（去重后可能合并多个）
    event: str                 # Claude Code hook 事件，如 "Stop"
    title: str
    rationale: str             # 为什么：N/M 复现 + 该 hook 如何拦截（确定性模板）
    command: str               # hook 运行的现有 agentops 命令
    settings_snippet: str      # 可直接采纳的 settings.json 片段（确定性渲染）
    evidence: tuple[str, ...]  # N/M + 热点路径
    def to_dict(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class ImprovementAssets:
    """Phase 6 总产物：RepoMemory + 现有指令文件 → 可采纳的改进资产（确定性投影）。"""
    repo_root: str
    sample_count: int
    trend_summary: str                                       # 趋势的一句话确定性摘要
    instruction_suggestions: tuple[InstructionSuggestion, ...]  # CLAUDE.md、AGENTS.md（固定顺序）
    hook_proposals: tuple[HookProposal, ...]
    skill_candidates: tuple[SkillCandidate, ...]             # 透传 memory 的 skill 候选 → skill 脚手架
    workflow_steps: tuple[str, ...]                          # 推荐运行节奏（确定性）
    def to_dict(self) -> dict[str, object]: ...
```

All models are immutable dataclasses with stable, JSON-friendly `to_dict()` (tuples → lists, `None` preserved, nested `Recommendation` / `Finding` / `SkillCandidate` serialized via their own `to_dict()`), matching the rest of `core/`.

### Asset narrator seam (shaped, deterministic default only)

```python
# agentops/improve/narrator.py

@runtime_checkable
class AssetNarrator(Protocol):
    """资产叙述接缝：把确定性资产草案富化为更可读的建议文本 / 减法诊断。

    Phase 6 只提供确定性默认实现；LLM 叙述者留到后续可选切片按同一接口填充，
    且只能改写描述字段（managed_block 的散文、rationale、trend_summary、Finding.message），
    绝不改动结构事实（target / 规则 kind / hook 命令 / 计数 / 证据路径），
    与 LLM 意图判官“绝不重新推导文件集合”、记忆叙述者“绝不改动 code/计数”同构。
    """
    def narrate(self, assets: ImprovementAssets) -> ImprovementAssets: ...


class DeterministicAssetNarrator:
    """默认叙述者：直接返回确定性模板投影，不改写、不触网、不需 key。"""
    def narrate(self, assets: ImprovementAssets) -> ImprovementAssets:
        return assets
```

This mirrors `IntentJudge` + `DeterministicIntentJudge` and `MemoryNarrator` + `DeterministicMemoryNarrator`: the seam exists and is injectable now, but the only behavior this slice ships is deterministic. Filling it with an LLM narrator later must not change the seam's shape or the structural facts.

### Instruction suggestions (new, deterministic)

```python
# agentops/improve/instructions.py

# 指令文件行预算（provisional）：CLAUDE.md 每轮注入上下文，过长挤占有效 token；
# 与 scope 扣分权重、记忆复现阈值一样待累积数据校准。
INSTRUCTION_LINE_BUDGET = 200

REPO_RULES_BLOCK_START = "<!-- agentops:repo-rules:start -->"
REPO_RULES_BLOCK_END = "<!-- agentops:repo-rules:end -->"

def derive_instruction_suggestions(
    memory: RepoMemory,
    instructions: dict[str, str | None],   # {"CLAUDE.md": content|None, "AGENTS.md": content|None}
    readme: str | None = None,
) -> tuple[InstructionSuggestion, ...]:
    """把规则候选投影为每个指令文件的加法托管块 + 确定性减法诊断。

    输入是文本内容（不是路径），保持投影纯函数、可离线测试——
    与 build_repo_memory 接收 records 而非路径同构。
    """
```

Deterministic rules (provisional thresholds flagged as such, to be calibrated from accumulated data):

- **Targets & order**: always emit suggestions for `CLAUDE.md` then `AGENTS.md`, in that fixed order, regardless of which exist.
- **加法 (additions)**: `additions = memory.rule_candidates` (already `Recommendation`s, in memory's stable order). When the target file is missing (`content is None`), *prepend* one `Recommendation(kind=ADD_CONSTRAINT_FILE, …)` recommending the file be created with the managed block.
- **managed_block**: render the `agentops:repo-rules` markers around one `- ` bullet per rule candidate (`title` — `action`). When there are zero rule candidates, `managed_block = ""` (the writer renders an explicit "no recurring rules distilled yet" note instead). Deterministic, stable order, LF line endings inside the rendered block.
- **减法 (subtractions)** — only when `content is not None`:
  - line budget: if `line_count > INSTRUCTION_LINE_BUDGET`, emit `Finding(code="instruction_over_budget", severity=WARNING, message="…N lines (budget 200); trim tutorial/redundant content…", evidence=("{N} lines",))`;
  - README duplication: if `readme` is present and the instruction file contains the README's first non-empty paragraph verbatim, emit `Finding(code="duplicates_readme", severity=INFO, message="…move project intro to the README…", evidence=(<the duplicated heading/first line>,))`.
- `line_count` counts lines deterministically (`content.splitlines()`); an empty existing file has `line_count == 0`.

The exact message wording and the README-paragraph extraction belong in implementation code and tests; keep both conservative — false-positive trim advice is worse than silence.

### Hook proposals (new, deterministic)

```python
# agentops/improve/hooks.py

# 失败模式 code → (hook 事件, 建议运行的现有 agentops 命令)。复用 Phase 5 的复现阈值。
_HOOK_FOR_CODE: dict[str, tuple[str, str]] = {
    "undeclared_change":    ("Stop", "agentops check-session-log --repo ."),
    "declared_not_changed": ("Stop", "agentops check-session-log --repo ."),
    "cross_module_breadth": ("Stop", "agentops eval --repo ."),
    CONFIRMED_DRIFT:        ("Stop", "agentops eval --repo ."),
}

def derive_hook_proposals(
    modes: tuple[FailureMode, ...],
) -> tuple[HookProposal, ...]:
    """为达到复现阈值的失败模式产出 hook 提案；按 (event, command) 去重合并证据。"""
```

Deterministic rules:

- only modes with `occurrence_count >= RECURRENCE_THRESHOLD` (reuse the Phase 5 constant) produce a proposal — sub-threshold modes are ignored, exactly as rule/skill candidates are gated;
- modes that map to the **same** `(event, command)` collapse into **one** proposal (all current scope failure modes → one Stop / `eval` proposal), with `failure_codes` listing all contributing codes and `evidence` merging their N/M + hot paths; deterministic order (by command, then first contributing code);
- `settings_snippet` is a deterministically rendered `settings.json` `hooks` fragment for that event + command (stable key order, two-space indent), copy-paste-ready and aligned with the `update-config` skill's hook shape;
- `rationale` cites the recurrence ("`undeclared_change` recurred in N/M evals; a Stop hook running `agentops eval` reconciles the latest declaration against git truth").

The mapped command already exists (`eval` since Phase 4) — Phase 6 proposes wiring it, it does not invent new runtime behavior.

### Improvement projection (new)

```python
# agentops/improve/aggregate.py

def build_improvement_assets(
    memory: RepoMemory,
    *,
    repo_root: str,
    instructions: dict[str, str | None],
    readme: str | None = None,
    narrator: AssetNarrator | None = None,
) -> ImprovementAssets:
    """把 RepoMemory + 现有指令文件确定性地投影为可采纳的改进资产；narrator 默认身份实现。"""
```

- `trend_summary`: a deterministic one-liner from `memory.trend` (e.g. "Scope-discipline trend is **worsening** over 6 evals (95→70); 4 drift verdicts.").
- `instruction_suggestions = derive_instruction_suggestions(memory, instructions, readme)`.
- `hook_proposals = derive_hook_proposals(memory.failure_modes)`.
- `skill_candidates = memory.skill_candidates` (passthrough — the writer renders skill scaffolds from them).
- `workflow_steps`: a deterministic recommended cadence (run `agentops eval` after each task; refresh `agentops memory` / `agentops suggest` when the trend is `worsening` or new failure modes appear).
- `narrator` default = `DeterministicAssetNarrator`; the projection is built first, then handed to `narrator.narrate(...)`.

Determinism is a hard requirement: the same `(memory, instructions, readme)` always yield an identical `ImprovementAssets` (stable ordering, no clock/random in the projection).

### Improvement artifacts (new writer)

```python
# agentops/writers/improvement_report.py

class ImprovementReportWriter:
    """写出改进资产产物：覆盖写出，绝不 append（资产是记忆+指令文件的可再生投影）。"""
    def write(self, assets: ImprovementAssets, output_dir: Path) -> tuple[Artifact, ...]:
        # suggested-claude-md.md   CLAUDE.md 的：可采纳 repo-rules 块 + 减法诊断 + 缺失提示
        # suggested-agents-md.md   AGENTS.md 的同形产物
        # suggested-hooks.md       hook 提案 + settings.json 片段 + 工作流指引 + skill 脚手架
        # agentops-suggestions.json 镜像 ImprovementAssets.to_dict()（UTF-8、sort_keys、两空格缩进、尾随换行）
        ...
```

Add `SUGGESTED_CLAUDE_MD`, `SUGGESTED_AGENTS_MD`, `HOOK_PROPOSALS`, `SUGGESTIONS_JSON` to `ArtifactKind`. All files are overwritten on each run. The two `suggested-*.md` drafts present the managed block inside a fenced code block so it is unambiguously copy-paste-able. The writer follows `MemoryReportWriter`'s conventions (deterministic ordering, `n/a` for `None`, backtick-quoted paths, single trailing newline).

### Suggest workflow runtime (new)

```python
# agentops/runtime/improve.py

@dataclass(frozen=True)
class ImproveRunResult:
    assets: ImprovementAssets
    artifacts: tuple[Artifact, ...]
    trace: WorkflowTrace


class ImproveWorkflowError(RuntimeError):
    """暴露 suggest 流程失败时保留下来的 workflow trace（沿用 scan/eval/memory 语义）。"""


def run_suggest(
    repo_path: Path,
    history_path: Path,
    output_dir: Path,
    *,
    narrator: AssetNarrator | None = None,
    timestamp: datetime | None = None,
) -> ImproveRunResult:
    """编排 read_history → build_memory → read_instructions → build_assets → write_improvement_artifacts。"""
```

Steps run through the same `WorkflowRunner`: `read_history` → `build_memory` → `read_instructions` → `build_assets` → `write_improvement_artifacts`, with a trace written via `TraceWriter` exactly as scan / eval / memory do. `read_history` and `build_memory` reuse Phase 5 (`EvalHistoryReader`, `build_repo_memory`) unchanged — including the missing-file / zero-records structured failure with the "run agentops eval first" guidance. `read_instructions` reads `CLAUDE.md` / `AGENTS.md` / `README.md` from `repo_path` read-only into the `instructions` / `readme` inputs (a missing file → `None`, never an error). The default narrator is `DeterministicAssetNarrator` — no LLM, no network, no key.

### CLI wiring (new command)

- `agentops suggest --repo <p> [--history <jsonl>] [--output <dir>]`; `--history` defaults to `<repo>/.agentops/eval-history.jsonl`, `--output` defaults to `.agentops`.
- A thin adapter over `run_suggest`, mirroring the `memory` adapter: structured `ImproveWorkflowError` → exit 1 with a concise stderr line (the preserved failure message, e.g. "run agentops eval first") and the trace path (when written), no traceback; unexpected exceptions are not swallowed.
- On success, print one summary line — sample count, trend direction, and counts of instruction suggestions / hook proposals / skill candidates — then one `Wrote <path>` line per artifact.
- `scan`, `eval`, `memory`, `init`, and `check-session-log` parsers and behavior are untouched.

## Task 1: Asset core models

**Files:** `agentops/core/asset.py`, `agentops/core/artifact.py`, `tests/test_asset_models.py`.

- [x] Write failing tests: `InstructionSuggestion`, `HookProposal`, `ImprovementAssets` are frozen and serialize via `to_dict()` (tuples → lists, `None` preserved, nested `Recommendation` / `Finding` / `SkillCandidate` serialized); `ImprovementAssets.to_dict()` round-trips a representative instance; `ArtifactKind` gains `SUGGESTED_CLAUDE_MD` / `SUGGESTED_AGENTS_MD` / `HOOK_PROPOSALS` / `SUGGESTIONS_JSON`.
- [x] Confirm failure, implement the dataclasses + enum additions (pure stdlib, Chinese comments), run tests (PASS).
- [x] Commit `feat: add improvement-asset core models`.

## Task 2: Instruction suggestions projection

**Files:** `agentops/improve/__init__.py`, `agentops/improve/instructions.py`, `tests/test_improve_instructions.py`.

- [x] Write failing tests: `derive_instruction_suggestions` emits suggestions for `CLAUDE.md` then `AGENTS.md` in fixed order; additions reuse `memory.rule_candidates`; a missing file (`None`) sets `exists=False`, `line_count=None`, prepends an `ADD_CONSTRAINT_FILE` recommendation, and still renders a managed block; the `agentops:repo-rules` block has one bullet per rule candidate and is empty (`""`) when there are no rule candidates; an over-budget existing file yields `instruction_over_budget` (WARNING); an instruction file containing the README's first paragraph yields `duplicates_readme` (INFO); no false-positive trim findings on a short, non-duplicating file.
- [x] Confirm failure, implement the deterministic projection (provisional `INSTRUCTION_LINE_BUDGET`, documented in code), run tests (PASS).
- [x] Commit `feat: project rule candidates into instruction suggestions`.

## Task 3: Hook proposals projection

**Files:** `agentops/improve/hooks.py`, `tests/test_improve_hooks.py`.

- [x] Write failing tests: `derive_hook_proposals` emits one proposal per distinct `(event, command)` for failure modes at or above the recurrence threshold; sub-threshold modes emit nothing; all current scope failure modes collapse into one Stop / `eval` proposal because `eval` is the existing command that reconciles declarations against git truth; `settings_snippet` is the deterministic, copy-paste `settings.json` fragment; output order is stable.
- [x] Confirm failure, implement (reuse `RECURRENCE_THRESHOLD` / `CONFIRMED_DRIFT`), run tests (PASS).
- [x] Commit `feat: propose hooks from recurring failure modes`.

## Task 4: Projection assembly and narrator seam

**Files:** `agentops/improve/aggregate.py`, `agentops/improve/narrator.py`, `agentops/improve/__init__.py`, `tests/test_improve_aggregate.py`.

- [x] Write failing tests: `build_improvement_assets(memory, repo_root=…, instructions=…, readme=…, narrator=None)` composes `trend_summary` + instruction suggestions + hook proposals + passthrough skill candidates + workflow steps into an `ImprovementAssets`; the **same inputs yield an identical `ImprovementAssets`** (determinism); `DeterministicAssetNarrator` is the default and returns the projection unchanged; an injected stub narrator is invoked and may rewrite only description fields (assert structural facts — targets / rule kinds / hook commands / counts / paths — are unchanged); `AssetNarrator` is a `runtime_checkable` `Protocol` the stub satisfies; a **thin** memory (no recurring modes) yields empty hook proposals, empty managed blocks, and a clear trend summary without raising.
- [x] Confirm failure, implement the projection + seam, export from `improve/__init__.py`, run tests (PASS).
- [x] Commit `feat: assemble improvement assets behind a narrator seam`.

## Task 5: Improvement artifacts writer

**Files:** `agentops/writers/improvement_report.py`, `tests/test_improvement_report_writer.py`.

- [x] Write failing tests: `ImprovementReportWriter.write` produces `suggested-claude-md.md` and `suggested-agents-md.md` (each: a fenced, adoptable repo-rules block or the "no recurring rules yet" note; a trim-diagnostics section; a missing-file note when applicable), `suggested-hooks.md` (hook proposals + `settings.json` snippets + workflow steps + skill scaffolds), and `agentops-suggestions.json` mirroring `ImprovementAssets.to_dict()` (sorted keys, trailing newline); all are **overwritten** on a second run (not appended); a thin/empty assets instance renders cleanly with stable ordering.
- [x] Confirm failure, implement the writer returning the four `Artifact`s, run tests (PASS).
- [x] Commit `feat: write suggested instruction, hook, and suggestions artifacts`.

## Task 6: Suggest workflow runtime and CLI

**Files:** `agentops/runtime/improve.py`, `agentops/cli.py`, `tests/test_improve_runtime.py`, `tests/test_cli.py`.

- [x] Write failing tests: `run_suggest(repo, history, output)` reads history, builds memory, reads instructions read-only, builds assets, writes the four artifacts + `agentops-trace.json`, and returns an `ImproveRunResult`; a missing history file and a zero-valid-records history each raise a structured `ImproveWorkflowError` with a preserved trace and the "run agentops eval first" message; the target repo's `CLAUDE.md` / `AGENTS.md` / `README.md` are not modified; the default narrator makes no LLM/network call. `agentops suggest --repo <p>` prints the summary + artifact paths and writes the artifacts; `--history` / `--output` honored; structured failure → exit 1, concise stderr, no traceback; `scan` / `eval` / `memory` / `init` / `check-session-log` unchanged.
- [x] Confirm failure, implement `run_suggest` (compose via `WorkflowRunner`, reuse `EvalHistoryReader` / `build_repo_memory` / `TraceWriter`) and the thin CLI adapter, run tests (PASS).
- [x] Commit `feat: expose the agentops suggest command`.

## Task 7: Document and verify

**Files:** `README.md`, `README.en.md`, `docs/architecture.md`, `docs/development-roadmap.md`, `docs/README.md`, `docs/project-memory.md`, `agent.md`.

- [x] Update READMEs (zh+en) with `agentops suggest` usage and the five outputs; record in `architecture.md` the suggest pipeline, the `AssetNarrator` seam, the "suggest-not-rewrite / read-only target repo / distinct repo-rules markers / verdict does not move the score" boundary, the `agentops/improve/` module row, and the new `ArtifactKind`s; in `development-roadmap.md` mark **Phase 6 complete** and set the next step to **Phase 7 supervisory loop** (and note the still-open score-calibration question + the still-deferred optional LLM narrators for both memory and assets); refresh `project-memory.md` (files, test count, decisions, commits) and `agent.md`'s "当前下一步"; mark this plan **已完成** in `docs/README.md`.
- [x] Run `python -m pytest -v` (all pass). Verify end-to-end against this repo: `agentops suggest --repo .` re-projects the real `eval-history.jsonl`, reads this repo's `CLAUDE.md`/`AGENTS.md`/`README.md` read-only, writes the four suggestion artifacts + trace, exits 0, and leaves the tracked worktree clean (read-only except `--output`). Confirm a second run overwrites (not appends) and is byte-identical, and that the target instruction files are untouched.
- [x] Commit `docs: record phase 6 improvement assets`.

## Parallel Development Guidance

Start sequentially (shared contracts):

```text
asset core models (Task 1)
-> instruction suggestions (Task 2) + hook proposals (Task 3)  [parallel]
-> assembly + seam (Task 4)
-> writer (Task 5) + runtime/CLI (Task 6)  [parallel after Task 4 stabilizes ImprovementAssets]
```

Once Task 1 fixes the `ImprovementAssets` / `InstructionSuggestion` / `HookProposal` contracts, the two deterministic projections (Tasks 2–3) can be developed in parallel against synthetic `RepoMemory` fixtures; Task 4 integrates them. After Task 4 stabilizes `ImprovementAssets`, the writer (Task 5) and the runtime + CLI (Task 6) can proceed in parallel. Keep `agentops/cli.py`, `agentops/core/artifact.py`, `agentops/improve/__init__.py`, `README.md`, and `docs/project-memory.md` edits on the integration path to avoid conflicts (same rule as Phase 5).

## Exit Criteria

Phase 6 is complete when:

- `agentops suggest --repo <path>` re-projects the accumulated `eval-history.jsonl` into `RepoMemory`, reads the repo's current instruction files read-only, and writes `suggested-claude-md.md`, `suggested-agents-md.md`, `suggested-hooks.md`, `agentops-suggestions.json`, and `agentops-trace.json`;
- the `CLAUDE.md` / `AGENTS.md` suggestions each carry an adoptable `agentops:repo-rules` managed block distilled from recurring rule candidates (加法), deterministic trim diagnostics (减法: over-budget length, README duplication), and a create-the-file note when the target is missing — all citing the same N/M historical evidence;
- the hook proposals map each recurring failure mode to an existing `agentops` command and a copy-paste `settings.json` snippet, gated by the recurrence threshold and deduplicated;
- the projection is reproducible: the same memory + instruction files yield byte-identical assets, and the artifacts are overwritten (not appended) on each run;
- the `AssetNarrator` seam exists with a deterministic identity default; `agentops suggest` makes no LLM/network/API-key call and adds no runtime dependency;
- `agentops suggest` is read-only with respect to the target repo (including its `CLAUDE.md` / `AGENTS.md` / `README.md`) except under `--output`; it never recomputes or moves any eval score; `core/eval.py`, `core/memory.py`, the scoring, and the eval/scan/memory/init/check pipelines are unchanged;
- a missing or empty history fails as a structured error (exit 1, concise stderr, no traceback); a thin history (one eval, or no mode reaching the recurrence threshold) still produces clean, well-noted assets;
- every test is deterministic and offline; `python -m pytest -v` passes.

The next step after Phase 6 is **Phase 7 supervisory loop**: a watcher / real-time supervision that observes AI coding work as it happens and surfaces interventions, plus trend analysis on top of the now-complete observe → evaluate → diagnose → improve chain. Two questions stay open for later, to be decided from the accumulating memory: whether `drift` trends justify letting the intent verdict calibrate the score, and whether to fill the `MemoryNarrator` / `AssetNarrator` seams with an optional LLM narrator.
