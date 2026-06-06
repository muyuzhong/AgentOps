from agentops.core.memory import FailureMode, SkillCandidate
from agentops.core.recommendation import Recommendation, RecommendationKind
from agentops.memory.candidates import (
    RECURRENCE_THRESHOLD,
    derive_rule_candidates,
    derive_skill_candidates,
)
from agentops.memory.failure_modes import CONFIRMED_DRIFT
from agentops.parsers.history import HistoryRecord


def _mode(
    code: str,
    *,
    occurrence_count: int,
    sample_count: int = 5,
    hot_paths: tuple[str, ...] = (),
    last_seen: str = "2026-06-06",
) -> FailureMode:
    return FailureMode(
        code=code,
        occurrence_count=occurrence_count,
        sample_count=sample_count,
        hot_paths=hot_paths,
        last_seen=last_seen,
        summary="s",
    )


def _records(count: int) -> tuple[HistoryRecord, ...]:
    return tuple(
        HistoryRecord(timestamp=f"t{index}", result={}, verdict_summary={})
        for index in range(count)
    )


# ---- rule candidates -------------------------------------------------------


def test_rule_candidate_per_recurring_mode_uses_kind_mapping() -> None:
    modes = (
        _mode("undeclared_change", occurrence_count=3),
        _mode("declared_not_changed", occurrence_count=2),
        _mode("cross_module_breadth", occurrence_count=2),
        _mode(CONFIRMED_DRIFT, occurrence_count=2),
    )

    rules = derive_rule_candidates(modes)

    # 每个达到阈值的失败模式产出一条建议，复用 eval 路径已确立的 kind 映射。
    assert [rule.kind for rule in rules] == [
        RecommendationKind.DECLARE_CHANGED_FILES,
        RecommendationKind.REVIEW_DECLARED_CHANGES,
        RecommendationKind.REVIEW_SCOPE_BOUNDARY,
        RecommendationKind.REVIEW_SCOPE_BOUNDARY,
    ]
    assert all(isinstance(rule, Recommendation) for rule in rules)


def test_rule_candidate_rationale_cites_recurrence_and_hot_paths() -> None:
    modes = (
        _mode(
            "undeclared_change",
            occurrence_count=3,
            sample_count=5,
            hot_paths=("src/billing.py", "src/auth.py"),
        ),
    )

    rule = derive_rule_candidates(modes)[0]

    # 规则候选的 rationale 必须带 N/M 复现证据与热点路径。
    assert "3/5" in rule.rationale
    assert "src/billing.py" in rule.rationale


def test_sub_threshold_modes_emit_no_rule_candidates() -> None:
    modes = (
        _mode("undeclared_change", occurrence_count=RECURRENCE_THRESHOLD - 1),
    )

    assert derive_rule_candidates(modes) == ()


def test_rule_candidates_preserve_incoming_mode_order() -> None:
    # modes 已按出现次数降序传入；候选保持同序，确定性。
    modes = (
        _mode("undeclared_change", occurrence_count=4),
        _mode("declared_not_changed", occurrence_count=2),
    )

    rules = derive_rule_candidates(modes)

    assert rules[0].kind == RecommendationKind.DECLARE_CHANGED_FILES
    assert rules[1].kind == RecommendationKind.REVIEW_DECLARED_CHANGES


# ---- skill candidates ------------------------------------------------------


def test_skill_candidate_for_recurring_undeclared_change_carries_evidence() -> None:
    modes = (
        _mode(
            "undeclared_change",
            occurrence_count=3,
            sample_count=4,
            hot_paths=("src/billing.py",),
        ),
    )

    skills = derive_skill_candidates(modes, _records(4))

    assert len(skills) == 1
    skill = skills[0]
    assert isinstance(skill, SkillCandidate)
    assert skill.slug == "declare-changed-files-checklist"
    # 历史证据带 N/M 复现 + 相关路径。
    assert any("3/4" in item for item in skill.evidence)
    assert any("src/billing.py" in item for item in skill.evidence)


def test_skill_candidate_for_scope_modes_incorporates_dominant_module() -> None:
    modes = (
        _mode(
            "cross_module_breadth",
            occurrence_count=2,
            sample_count=3,
            hot_paths=("src", "tests", "docs"),
        ),
    )

    skill = derive_skill_candidates(modes, _records(3))[0]

    # 主导模块（最热证据）进入 slug，保持确定性、可读。
    assert "src" in skill.slug


def test_no_recurrence_no_skill_candidates() -> None:
    modes = (
        _mode("undeclared_change", occurrence_count=RECURRENCE_THRESHOLD - 1),
    )

    assert derive_skill_candidates(modes, _records(5)) == ()


def test_skill_candidates_are_deterministic_and_slug_unique() -> None:
    # cross_module_breadth 与 confirmed_drift 都集中在同一模块 src：
    # 两者都映射到 scope-boundary skill，应按 slug 去重为一个。
    modes = (
        _mode(
            "cross_module_breadth",
            occurrence_count=3,
            sample_count=4,
            hot_paths=("src", "tests", "docs"),
        ),
        _mode(
            CONFIRMED_DRIFT,
            occurrence_count=2,
            sample_count=4,
            hot_paths=("src/auth.py",),
        ),
    )

    first = derive_skill_candidates(modes, _records(4))
    second = derive_skill_candidates(modes, _records(4))

    # 同样输入产出字节一致的候选。
    assert first == second
    slugs = [skill.slug for skill in first]
    assert len(slugs) == len(set(slugs))
