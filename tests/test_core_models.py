from pathlib import Path

import pytest

from agentops.core.artifact import Artifact, ArtifactKind
from agentops.core.evaluation import Finding, ReadinessReport, Severity
from agentops.core.recommendation import Recommendation, RecommendationKind
from agentops.core.repo import RepoProfile


def test_repo_profile_serializes_paths_as_strings() -> None:
    profile = RepoProfile(
        root=Path("demo"),
        has_readme=True,
        constraint_files=("AGENTS.md",),
    )

    assert profile.to_dict()["root"] == "demo"
    assert profile.to_dict()["constraint_files"] == ["AGENTS.md"]


def test_repo_profile_serializes_test_commands() -> None:
    profile = RepoProfile(
        root=Path("demo"),
        test_commands=("python -m pytest",),
    )

    assert profile.to_dict()["test_commands"] == ["python -m pytest"]


def test_recommendation_exposes_actionable_fields() -> None:
    recommendation = Recommendation(
        kind=RecommendationKind.ADD_CONSTRAINT_FILE,
        title="Add AGENTS.md",
        rationale="The repository has no agent instructions.",
        action="Create an AGENTS.md file with test commands and boundaries.",
    )

    assert recommendation.to_dict()["kind"] == "add_constraint_file"


def test_readiness_report_serializes_findings_and_recommendations() -> None:
    report = ReadinessReport(
        profile=RepoProfile(root=Path("demo")),
        score=75,
        findings=(
            Finding(
                code="missing_agents_md",
                severity=Severity.WARNING,
                message="AGENTS.md is missing.",
                evidence=("AGENTS.md",),
            ),
        ),
        recommendations=(
            Recommendation(
                kind=RecommendationKind.ADD_CONSTRAINT_FILE,
                title="Add AGENTS.md",
                rationale="The repository has no agent instructions.",
                action="Create an AGENTS.md file with test commands and boundaries.",
            ),
        ),
    )

    data = report.to_dict()
    assert data["score"] == 75
    assert data["findings"][0]["severity"] == "warning"
    assert data["findings"][0]["evidence"] == ["AGENTS.md"]
    assert data["recommendations"][0]["kind"] == "add_constraint_file"


def test_artifact_serializes_kind_and_path() -> None:
    artifact = Artifact(kind=ArtifactKind.MARKDOWN_REPORT, path=Path("report.md"))

    assert artifact.to_dict() == {
        "kind": "markdown_report",
        "path": "report.md",
    }


@pytest.mark.parametrize("score", [-1, 101, 50.5, True, False, "50", None])
def test_readiness_report_rejects_invalid_scores(score: object) -> None:
    with pytest.raises(ValueError, match="score must be between 0 and 100"):
        ReadinessReport(profile=RepoProfile(root=Path("demo")), score=score)


@pytest.mark.parametrize("score", [0, 100])
def test_readiness_report_accepts_boundary_scores(score: int) -> None:
    report = ReadinessReport(profile=RepoProfile(root=Path("demo")), score=score)

    assert report.score == score
