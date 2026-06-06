"""从反复出现的失败模式派生规则候选与 skill 候选（确定性投影）。

两者都是**候选数据**，不是最终资产：把它们落成 CLAUDE.md / AGENTS.md 文本、hook 或
workflow 资产是 Phase 6 的事。本模块只做确定性蒸馏——

- ``derive_rule_candidates`` 为每个达到复现阈值的失败模式产出一条 ``Recommendation``，
  复用 eval 路径已确立的 code→kind 映射，rationale 带 N/M 复现与热点路径证据；不新增模型。
- ``derive_skill_candidates`` 把同样的复现模式提炼为带确定性 slug 的 ``SkillCandidate``，
  scope-boundary 两类再按主导模块细化 slug，每条带 N/M + 路径证据。

复现阈值是 provisional 的（与 scope 扣分权重同样缺乏真实数据支撑），待累积历史校准。
"""

from __future__ import annotations

import re

from agentops.core.memory import FailureMode, SkillCandidate
from agentops.core.recommendation import Recommendation, RecommendationKind
from agentops.memory.failure_modes import CONFIRMED_DRIFT
from agentops.parsers.history import HistoryRecord

# 复现阈值（provisional）：失败模式至少出现在这么多次评测里，才值得产出候选。
RECURRENCE_THRESHOLD = 2

# 横跨多个顶层模块 / LLM 确认漂移两类都归到“审查 scope 边界”这条规则。
_SCOPE_BOUNDARY_CODES = ("cross_module_breadth", CONFIRMED_DRIFT)

# 失败模式 code → 规则建议类型（复用 eval 路径已确立的映射，不另立新 kind）。
_RULE_KINDS: dict[str, RecommendationKind] = {
    "undeclared_change": RecommendationKind.DECLARE_CHANGED_FILES,
    "declared_not_changed": RecommendationKind.REVIEW_DECLARED_CHANGES,
    "cross_module_breadth": RecommendationKind.REVIEW_SCOPE_BOUNDARY,
    CONFIRMED_DRIFT: RecommendationKind.REVIEW_SCOPE_BOUNDARY,
}

# 每种 code 的规则候选标题与行动（确定性模板；rationale 另带 N/M 历史证据）。
_RULE_TEXT: dict[str, tuple[str, str]] = {
    "undeclared_change": (
        "Declare every changed file before ending the session",
        "Add every touched path to the task report's Changed Files section before "
        "ending the session.",
    ),
    "declared_not_changed": (
        "Align declared files with git truth",
        "Remove stale path claims or verify that the intended file was actually changed.",
    ),
    "cross_module_breadth": (
        "Review task scope boundaries",
        "Split broad changes into smaller tasks or explain the cross-module coupling.",
    ),
    CONFIRMED_DRIFT: (
        "Address recurring confirmed scope drift",
        "The intent judge repeatedly confirmed drift on these paths; scope them into a "
        "dedicated task or justify the coupling before changing them.",
    ),
}


def derive_rule_candidates(
    modes: tuple[FailureMode, ...],
) -> tuple[Recommendation, ...]:
    """为每个达到复现阈值的失败模式产出一条带 N/M 证据的规则候选。

    输入 ``modes`` 已按出现次数降序、code 升序排好；输出保持同序，确定性。
    """

    candidates: list[Recommendation] = []
    for mode in modes:
        if mode.occurrence_count < RECURRENCE_THRESHOLD:
            continue
        kind = _RULE_KINDS.get(mode.code)
        if kind is None:
            continue
        title, action = _RULE_TEXT[mode.code]
        candidates.append(
            Recommendation(
                kind=kind,
                title=title,
                rationale=_evidence_sentence(mode),
                action=action,
            )
        )
    return tuple(candidates)


def derive_skill_candidates(
    modes: tuple[FailureMode, ...],
    records: tuple[HistoryRecord, ...],
) -> tuple[SkillCandidate, ...]:
    """从达到复现阈值的失败模式提炼可复用的 skill 候选。

    ``records`` 提供 N/M 证据里的分母 M（评测窗口大小，权威来源即历史本身）。
    scope-boundary 两类会按主导模块细化 slug，可能撞车——按 slug 去重，保留先到者
    （即出现次数更高的模式），保证同样输入产出同样、无重复 slug 的候选。
    """

    sample_count = len(records)
    candidates: list[SkillCandidate] = []
    seen: set[str] = set()
    for mode in modes:
        if mode.occurrence_count < RECURRENCE_THRESHOLD:
            continue
        candidate = _skill_for(mode, sample_count)
        if candidate is None or candidate.slug in seen:
            continue
        seen.add(candidate.slug)
        candidates.append(candidate)
    return tuple(candidates)


def _skill_for(mode: FailureMode, sample_count: int) -> SkillCandidate | None:
    """把单个失败模式映射为 skill 候选；未知 code 返回 None。"""

    evidence = _skill_evidence(mode, sample_count)

    if mode.code == "undeclared_change":
        return SkillCandidate(
            slug="declare-changed-files-checklist",
            title="Changed-files declaration checklist",
            trigger="Before ending any coding session that edits more than one file.",
            rationale=(
                "Undeclared changes recur across evals; a pre-flight checklist that "
                "lists every touched path keeps the declaration honest."
            ),
            evidence=evidence,
        )
    if mode.code == "declared_not_changed":
        return SkillCandidate(
            slug="reconcile-declared-files-checklist",
            title="Declared-files reconciliation checklist",
            trigger="Before ending a session whose task report names specific files.",
            rationale=(
                "Declared-but-unchanged files recur across evals; reconcile each "
                "claimed path against the diff before finishing."
            ),
            evidence=evidence,
        )
    if mode.code in _SCOPE_BOUNDARY_CODES:
        module = _dominant_module(mode.hot_paths)
        suffix = f"-{module}" if module else ""
        focus = f" especially `{module}`" if module else ""
        title = (
            f"Scope-boundary checklist for `{module}`"
            if module
            else "Scope-boundary checklist"
        )
        return SkillCandidate(
            slug=f"review-scope-boundary{suffix}-checklist",
            title=title,
            trigger=(
                "Before changing files that span multiple top-level modules"
                f"{focus}."
            ),
            rationale=(
                "Scope drift recurs across evals; a boundary checklist forces an "
                "explicit decision to split the work or justify the coupling."
            ),
            evidence=evidence,
        )
    return None


def _evidence_sentence(mode: FailureMode) -> str:
    """规则候选 rationale：N/M 复现 + 最近出现 + 热点路径（确定性模板）。"""

    paths = ", ".join(mode.hot_paths) if mode.hot_paths else "none"
    return (
        f"'{mode.code}' recurred in {mode.occurrence_count}/{mode.sample_count} evals "
        f"(last seen {mode.last_seen}); hot paths: {paths}."
    )


def _skill_evidence(mode: FailureMode, sample_count: int) -> tuple[str, ...]:
    """skill 候选证据：N/M 复现（M 取自历史窗口）+ 热点路径。"""

    recurrence = (
        f"recurred in {mode.occurrence_count}/{sample_count} evals "
        f"(last seen {mode.last_seen})"
    )
    if mode.hot_paths:
        return (recurrence, "hot paths: " + ", ".join(mode.hot_paths))
    return (recurrence,)


def _dominant_module(hot_paths: tuple[str, ...]) -> str:
    """取最热证据路径的顶层模块并 slugify；无热点路径时返回空串。

    cross_module_breadth 的热点本身就是模块名（如 ``src``、``(root)``）；
    confirmed_drift 的热点是路径（如 ``src/auth.py``），取其首段即顶层模块。
    """

    if not hot_paths:
        return ""
    top = hot_paths[0]
    module = top.split("/", 1)[0] if "/" in top else top
    return _slugify(module)


def _slugify(text: str) -> str:
    """把任意 token 规范化为小写、连字符分隔的 slug 片段（如 ``(root)`` → ``root``）。"""

    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
