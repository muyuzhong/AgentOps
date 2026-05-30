from pathlib import Path

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
