import dataclasses
from pathlib import Path

import pytest

from agentops.core.artifact import ArtifactKind
from agentops.core.memory import (
    FailureMode,
    RepoMemory,
    ScoreTrend,
    SkillCandidate,
)
from agentops.core.recommendation import Recommendation, RecommendationKind


def _recommendation() -> Recommendation:
    return Recommendation(
        kind=RecommendationKind.DECLARE_CHANGED_FILES,
        title="Declare every changed file",
        rationale="Undeclared changes recurred in 3/5 evals.",
        action="List every touched path in the task declaration.",
    )


def test_score_trend_serializes_stably() -> None:
    trend = ScoreTrend(
        sample_count=3,
        first_score=70,
        last_score=85,
        average_score=78.5,
        direction="improving",
        drift_verdict_total=2,
    )

    assert trend.to_dict() == {
        "sample_count": 3,
        "first_score": 70,
        "last_score": 85,
        "average_score": 78.5,
        "direction": "improving",
        "drift_verdict_total": 2,
    }


def test_score_trend_preserves_none_for_empty_history() -> None:
    trend = ScoreTrend(
        sample_count=0,
        first_score=None,
        last_score=None,
        average_score=None,
        direction="unknown",
        drift_verdict_total=0,
    )

    data = trend.to_dict()
    assert data["first_score"] is None
    assert data["last_score"] is None
    assert data["average_score"] is None
    assert data["direction"] == "unknown"


def test_score_trend_is_frozen() -> None:
    trend = ScoreTrend(
        sample_count=1,
        first_score=80,
        last_score=80,
        average_score=80.0,
        direction="unknown",
        drift_verdict_total=0,
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        trend.direction = "improving"  # type: ignore[misc]


def test_failure_mode_serializes_tuples_as_lists() -> None:
    mode = FailureMode(
        code="undeclared_change",
        occurrence_count=3,
        sample_count=5,
        hot_paths=("src/auth.py", "src/billing.py"),
        last_seen="2026-06-06T12:00:00Z",
        summary="Undeclared changes recurred in 3/5 evals.",
    )

    assert mode.to_dict() == {
        "code": "undeclared_change",
        "occurrence_count": 3,
        "sample_count": 5,
        "hot_paths": ["src/auth.py", "src/billing.py"],
        "last_seen": "2026-06-06T12:00:00Z",
        "summary": "Undeclared changes recurred in 3/5 evals.",
    }


def test_failure_mode_is_frozen() -> None:
    mode = FailureMode(
        code="undeclared_change",
        occurrence_count=1,
        sample_count=1,
        hot_paths=(),
        last_seen="2026-06-06T12:00:00Z",
        summary="s",
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        mode.occurrence_count = 2  # type: ignore[misc]


def test_skill_candidate_serializes_evidence_as_list() -> None:
    candidate = SkillCandidate(
        slug="declare-changed-files-checklist",
        title="Declare changed files checklist",
        trigger="Before finishing a task that touches multiple files.",
        rationale="Undeclared changes recurred in 3/5 evals.",
        evidence=("3/5 evals", "src/auth.py"),
    )

    assert candidate.to_dict() == {
        "slug": "declare-changed-files-checklist",
        "title": "Declare changed files checklist",
        "trigger": "Before finishing a task that touches multiple files.",
        "rationale": "Undeclared changes recurred in 3/5 evals.",
        "evidence": ["3/5 evals", "src/auth.py"],
    }


def test_skill_candidate_is_frozen() -> None:
    candidate = SkillCandidate(
        slug="s",
        title="t",
        trigger="tr",
        rationale="r",
        evidence=(),
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        candidate.slug = "other"  # type: ignore[misc]


def test_repo_memory_serializes_nested_models(tmp_path: Path) -> None:
    trend = ScoreTrend(
        sample_count=2,
        first_score=70,
        last_score=80,
        average_score=75.0,
        direction="improving",
        drift_verdict_total=1,
    )
    mode = FailureMode(
        code="undeclared_change",
        occurrence_count=2,
        sample_count=2,
        hot_paths=("src/auth.py",),
        last_seen="2026-06-06T12:00:00Z",
        summary="Undeclared changes recurred in 2/2 evals.",
    )
    candidate = SkillCandidate(
        slug="declare-changed-files-checklist",
        title="Declare changed files checklist",
        trigger="Before finishing a multi-file task.",
        rationale="Undeclared changes recurred in 2/2 evals.",
        evidence=("2/2 evals", "src/auth.py"),
    )
    memory = RepoMemory(
        repo_root=str(tmp_path),
        sample_count=2,
        trend=trend,
        failure_modes=(mode,),
        rule_candidates=(_recommendation(),),
        skill_candidates=(candidate,),
    )

    assert memory.to_dict() == {
        "repo_root": str(tmp_path),
        "sample_count": 2,
        "trend": trend.to_dict(),
        "failure_modes": [mode.to_dict()],
        "rule_candidates": [_recommendation().to_dict()],
        "skill_candidates": [candidate.to_dict()],
    }


def test_repo_memory_rule_candidates_hold_recommendations() -> None:
    memory = RepoMemory(
        repo_root="demo",
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
        rule_candidates=(_recommendation(),),
        skill_candidates=(),
    )

    assert all(
        isinstance(candidate, Recommendation) for candidate in memory.rule_candidates
    )
    assert memory.to_dict()["rule_candidates"][0]["kind"] == "declare_changed_files"


def test_repo_memory_is_frozen() -> None:
    memory = RepoMemory(
        repo_root="demo",
        sample_count=0,
        trend=ScoreTrend(
            sample_count=0,
            first_score=None,
            last_score=None,
            average_score=None,
            direction="unknown",
            drift_verdict_total=0,
        ),
        failure_modes=(),
        rule_candidates=(),
        skill_candidates=(),
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        memory.sample_count = 1  # type: ignore[misc]


def test_artifact_kind_gains_memory_members() -> None:
    assert ArtifactKind.MEMORY_REPORT.value == "memory_report"
    assert ArtifactKind.MEMORY_JSON.value == "memory_json"
    assert ArtifactKind.SKILL_CANDIDATES.value == "skill_candidates"
