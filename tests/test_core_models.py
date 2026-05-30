from pathlib import Path

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
