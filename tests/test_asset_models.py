import dataclasses

import pytest

from agentops.core.artifact import ArtifactKind
from agentops.core.asset import HookProposal, ImprovementAssets, InstructionSuggestion
from agentops.core.evaluation import Finding, Severity
from agentops.core.memory import SkillCandidate
from agentops.core.recommendation import Recommendation, RecommendationKind


def _recommendation() -> Recommendation:
    return Recommendation(
        kind=RecommendationKind.DECLARE_CHANGED_FILES,
        title="Declare every changed file",
        rationale="Undeclared changes recurred in 3/5 evals.",
        action="List every touched path in the task declaration.",
    )


def _finding() -> Finding:
    return Finding(
        code="instruction_over_budget",
        severity=Severity.WARNING,
        message="CLAUDE.md has 250 lines (budget 200); trim redundant content.",
        evidence=("250 lines",),
    )


def _skill_candidate() -> SkillCandidate:
    return SkillCandidate(
        slug="declare-changed-files-checklist",
        title="Changed-files declaration checklist",
        trigger="Before ending a multi-file session.",
        rationale="Undeclared changes recur across evals.",
        evidence=("3/5 evals", "src/auth.py"),
    )


def test_instruction_suggestion_serializes_nested_models() -> None:
    block = "<!-- agentops:repo-rules:start -->\n- x\n<!-- agentops:repo-rules:end -->"
    suggestion = InstructionSuggestion(
        target="CLAUDE.md",
        exists=True,
        line_count=250,
        additions=(_recommendation(),),
        subtractions=(_finding(),),
        managed_block=block,
    )

    assert suggestion.to_dict() == {
        "target": "CLAUDE.md",
        "exists": True,
        "line_count": 250,
        "additions": [_recommendation().to_dict()],
        "subtractions": [_finding().to_dict()],
        "managed_block": block,
    }


def test_instruction_suggestion_preserves_none_line_count() -> None:
    suggestion = InstructionSuggestion(
        target="AGENTS.md",
        exists=False,
        line_count=None,
        additions=(),
        subtractions=(),
        managed_block="",
    )

    data = suggestion.to_dict()
    assert data["line_count"] is None
    assert data["exists"] is False
    assert data["additions"] == []
    assert data["subtractions"] == []


def test_instruction_suggestion_is_frozen() -> None:
    suggestion = InstructionSuggestion(
        target="CLAUDE.md",
        exists=True,
        line_count=10,
        additions=(),
        subtractions=(),
        managed_block="",
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        suggestion.target = "AGENTS.md"  # type: ignore[misc]


def test_hook_proposal_serializes_tuples_as_lists() -> None:
    proposal = HookProposal(
        slug="check-session-log-stop-hook",
        failure_codes=("declared_not_changed", "undeclared_change"),
        event="Stop",
        title="Reconcile declared files at session end",
        rationale="recurred in 2/3 evals",
        command="agentops check-session-log --repo .",
        settings_snippet='{\n  "hooks": {}\n}',
        evidence=("undeclared_change: 2/3 evals",),
    )

    assert proposal.to_dict() == {
        "slug": "check-session-log-stop-hook",
        "failure_codes": ["declared_not_changed", "undeclared_change"],
        "event": "Stop",
        "title": "Reconcile declared files at session end",
        "rationale": "recurred in 2/3 evals",
        "command": "agentops check-session-log --repo .",
        "settings_snippet": '{\n  "hooks": {}\n}',
        "evidence": ["undeclared_change: 2/3 evals"],
    }


def test_hook_proposal_is_frozen() -> None:
    proposal = HookProposal(
        slug="s",
        failure_codes=(),
        event="Stop",
        title="t",
        rationale="r",
        command="c",
        settings_snippet="{}",
        evidence=(),
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        proposal.slug = "other"  # type: ignore[misc]


def test_improvement_assets_serializes_nested_models() -> None:
    suggestion = InstructionSuggestion(
        target="CLAUDE.md",
        exists=True,
        line_count=10,
        additions=(_recommendation(),),
        subtractions=(_finding(),),
        managed_block="block",
    )
    proposal = HookProposal(
        slug="check-session-log-stop-hook",
        failure_codes=("undeclared_change",),
        event="Stop",
        title="t",
        rationale="r",
        command="agentops check-session-log --repo .",
        settings_snippet="{}",
        evidence=("2/3",),
    )
    skill = _skill_candidate()
    assets = ImprovementAssets(
        repo_root="/repo",
        sample_count=3,
        trend_summary="Scope-discipline trend is worsening over 3 evals.",
        instruction_suggestions=(suggestion,),
        hook_proposals=(proposal,),
        skill_candidates=(skill,),
        workflow_steps=("Run agentops eval after each task.",),
    )

    assert assets.to_dict() == {
        "repo_root": "/repo",
        "sample_count": 3,
        "trend_summary": "Scope-discipline trend is worsening over 3 evals.",
        "instruction_suggestions": [suggestion.to_dict()],
        "hook_proposals": [proposal.to_dict()],
        "skill_candidates": [skill.to_dict()],
        "workflow_steps": ["Run agentops eval after each task."],
    }


def test_improvement_assets_is_frozen() -> None:
    assets = ImprovementAssets(
        repo_root="/r",
        sample_count=0,
        trend_summary="s",
        instruction_suggestions=(),
        hook_proposals=(),
        skill_candidates=(),
        workflow_steps=(),
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        assets.sample_count = 1  # type: ignore[misc]


def test_artifact_kind_gains_suggestion_members() -> None:
    assert ArtifactKind.SUGGESTED_CLAUDE_MD.value == "suggested_claude_md"
    assert ArtifactKind.SUGGESTED_AGENTS_MD.value == "suggested_agents_md"
    assert ArtifactKind.HOOK_PROPOSALS.value == "hook_proposals"
    assert ArtifactKind.SUGGESTIONS_JSON.value == "suggestions_json"
