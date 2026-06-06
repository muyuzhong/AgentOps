from agentops.core.asset import ImprovementAssets
from agentops.core.memory import FailureMode, RepoMemory, ScoreTrend, SkillCandidate
from agentops.core.recommendation import Recommendation, RecommendationKind
from agentops.improve import (
    AssetNarrator,
    DeterministicAssetNarrator,
    build_improvement_assets,
)


def _rule() -> Recommendation:
    return Recommendation(
        kind=RecommendationKind.DECLARE_CHANGED_FILES,
        title="Declare every changed file",
        rationale="'undeclared_change' recurred in 2/2 evals.",
        action="List every touched path.",
    )


def _mode() -> FailureMode:
    return FailureMode(
        code="undeclared_change",
        occurrence_count=2,
        sample_count=2,
        hot_paths=("src/a.py",),
        last_seen="2026-06-06",
        summary="s",
    )


def _skill() -> SkillCandidate:
    return SkillCandidate(
        slug="declare-changed-files-checklist",
        title="Changed-files declaration checklist",
        trigger="Before ending a multi-file session.",
        rationale="r",
        evidence=("2/2 evals",),
    )


def _rich_memory() -> RepoMemory:
    return RepoMemory(
        repo_root="/repo",
        sample_count=2,
        trend=ScoreTrend(
            sample_count=2,
            first_score=90,
            last_score=80,
            average_score=85.0,
            direction="worsening",
            drift_verdict_total=1,
        ),
        failure_modes=(_mode(),),
        rule_candidates=(_rule(),),
        skill_candidates=(_skill(),),
    )


def _thin_memory() -> RepoMemory:
    return RepoMemory(
        repo_root="/repo",
        sample_count=1,
        trend=ScoreTrend(
            sample_count=1,
            first_score=80,
            last_score=80,
            average_score=80.0,
            direction="unknown",
            drift_verdict_total=0,
        ),
        failure_modes=(),
        rule_candidates=(),
        skill_candidates=(),
    )


_INSTRUCTIONS = {"CLAUDE.md": "# rules\n", "AGENTS.md": None}


def test_build_composes_projection() -> None:
    memory = _rich_memory()
    assets = build_improvement_assets(
        memory, repo_root="/repo", instructions=_INSTRUCTIONS, readme=None
    )

    assert isinstance(assets, ImprovementAssets)
    assert assets.repo_root == "/repo"
    assert assets.sample_count == 2
    assert "worsening" in assets.trend_summary
    assert [s.target for s in assets.instruction_suggestions] == [
        "CLAUDE.md",
        "AGENTS.md",
    ]
    # undeclared_change @ 2/2 复现 → 一条 hook 提案。
    assert assets.hook_proposals
    # skill 候选透传。
    assert assets.skill_candidates == memory.skill_candidates
    assert assets.workflow_steps
    assert any("agentops eval" in step for step in assets.workflow_steps)


def test_build_is_deterministic() -> None:
    memory = _rich_memory()
    first = build_improvement_assets(
        memory, repo_root="/repo", instructions=_INSTRUCTIONS
    )
    second = build_improvement_assets(
        memory, repo_root="/repo", instructions=_INSTRUCTIONS
    )

    # 同样输入产出字节一致的资产。
    assert first == second
    assert first.to_dict() == second.to_dict()


def test_default_narrator_matches_explicit_deterministic() -> None:
    memory = _rich_memory()
    default = build_improvement_assets(
        memory, repo_root="/r", instructions=_INSTRUCTIONS
    )
    explicit = build_improvement_assets(
        memory,
        repo_root="/r",
        instructions=_INSTRUCTIONS,
        narrator=DeterministicAssetNarrator(),
    )

    assert default == explicit


class _RewriteTrendNarrator:
    """只改写描述字段（trend_summary）的叙述者替身；绝不改动结构事实。"""

    def __init__(self) -> None:
        self.called = False

    def narrate(self, assets: ImprovementAssets) -> ImprovementAssets:
        self.called = True
        return ImprovementAssets(
            repo_root=assets.repo_root,
            sample_count=assets.sample_count,
            trend_summary=f"narrated: {assets.trend_summary}",
            instruction_suggestions=assets.instruction_suggestions,
            hook_proposals=assets.hook_proposals,
            skill_candidates=assets.skill_candidates,
            workflow_steps=assets.workflow_steps,
        )


def test_injected_narrator_invoked_rewrites_only_descriptions() -> None:
    memory = _rich_memory()
    narrator = _RewriteTrendNarrator()
    baseline = build_improvement_assets(
        memory, repo_root="/r", instructions=_INSTRUCTIONS
    )
    narrated = build_improvement_assets(
        memory, repo_root="/r", instructions=_INSTRUCTIONS, narrator=narrator
    )

    assert narrator.called, "injected narrator should be consulted"
    # 描述字段被改写。
    assert narrated.trend_summary.startswith("narrated: ")
    # 结构事实（targets / hook 命令 / failure_codes / skill slug / workflow steps）保持不变。
    assert [s.target for s in narrated.instruction_suggestions] == [
        s.target for s in baseline.instruction_suggestions
    ]
    assert [p.command for p in narrated.hook_proposals] == [
        p.command for p in baseline.hook_proposals
    ]
    assert [p.failure_codes for p in narrated.hook_proposals] == [
        p.failure_codes for p in baseline.hook_proposals
    ]
    assert [s.slug for s in narrated.skill_candidates] == [
        s.slug for s in baseline.skill_candidates
    ]
    assert narrated.workflow_steps == baseline.workflow_steps


def test_asset_narrator_is_runtime_checkable_protocol() -> None:
    assert isinstance(_RewriteTrendNarrator(), AssetNarrator)
    assert isinstance(DeterministicAssetNarrator(), AssetNarrator)


def test_thin_memory_yields_empty_hooks_and_blocks() -> None:
    assets = build_improvement_assets(
        _thin_memory(),
        repo_root="/r",
        instructions={"CLAUDE.md": "x", "AGENTS.md": "y"},
    )

    # 薄历史：无复现失败模式 → 空 hook、空托管块、但趋势摘要清晰，不抛异常。
    assert assets.hook_proposals == ()
    assert all(s.managed_block == "" for s in assets.instruction_suggestions)
    assert "unknown" in assets.trend_summary
