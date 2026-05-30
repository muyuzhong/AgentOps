from dataclasses import replace
from pathlib import Path

import pytest

from agentops.core.recommendation import RecommendationKind
from agentops.core.repo import RepoProfile
from agentops.evaluators.readiness import ReadinessEvaluator


def complete_profile() -> RepoProfile:
    return RepoProfile(
        root=Path("demo"),
        has_readme=True,
        constraint_files=("AGENTS.md",),
        test_directories=("tests",),
        ci_files=(".github/workflows/ci.yml",),
        project_markers=("pyproject.toml",),
        test_commands=("python -m pytest",),
    )


def test_evaluator_scores_complete_profile_as_ready() -> None:
    report = ReadinessEvaluator().evaluate(complete_profile())

    assert report.score == 100
    assert report.findings == ()
    assert report.recommendations == ()


def test_evaluator_explains_missing_agent_instructions() -> None:
    profile = RepoProfile(root=Path("demo"), has_readme=True)

    report = ReadinessEvaluator().evaluate(profile)

    assert report.score < 100
    assert any(item.code == "missing_agent_instructions" for item in report.findings)
    assert any(
        item.kind is RecommendationKind.ADD_CONSTRAINT_FILE
        for item in report.recommendations
    )


def test_evaluator_reports_every_missing_capability_deterministically() -> None:
    evaluator = ReadinessEvaluator()
    profile = RepoProfile(root=Path("demo"))

    report = evaluator.evaluate(profile)

    assert report.score == 0
    assert len(report.findings) == 6
    assert len(report.recommendations) == 6
    assert all(item.evidence for item in report.findings)
    assert all(item.action for item in report.recommendations)
    assert evaluator.evaluate(profile) == report


@pytest.mark.parametrize(
    ("profile", "expected_score", "finding_code", "recommendation_kind"),
    [
        (
            replace(complete_profile(), has_readme=False),
            85,
            "missing_readme",
            RecommendationKind.ADD_README,
        ),
        (
            replace(complete_profile(), constraint_files=()),
            75,
            "missing_agent_instructions",
            RecommendationKind.ADD_CONSTRAINT_FILE,
        ),
        (
            replace(complete_profile(), test_directories=()),
            75,
            "missing_test_directory",
            RecommendationKind.ADD_TESTS,
        ),
        (
            replace(complete_profile(), ci_files=()),
            85,
            "missing_ci_config",
            RecommendationKind.ADD_CI,
        ),
        (
            replace(complete_profile(), project_markers=()),
            90,
            "missing_project_marker",
            RecommendationKind.REVIEW_TEST_COMMANDS,
        ),
        (
            replace(complete_profile(), test_commands=()),
            90,
            "missing_test_command",
            RecommendationKind.REVIEW_TEST_COMMANDS,
        ),
    ],
)
def test_evaluator_applies_each_explicit_deduction(
    profile: RepoProfile,
    expected_score: int,
    finding_code: str,
    recommendation_kind: RecommendationKind,
) -> None:
    report = ReadinessEvaluator().evaluate(profile)

    assert report.score == expected_score
    assert [item.code for item in report.findings] == [finding_code]
    assert [item.kind for item in report.recommendations] == [recommendation_kind]
