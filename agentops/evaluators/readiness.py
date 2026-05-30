"""根据仓库画像生成可解释的 readiness 评分。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from agentops.core.evaluation import Finding, ReadinessReport, Severity
from agentops.core.recommendation import Recommendation, RecommendationKind
from agentops.core.repo import RepoProfile


@dataclass(frozen=True)
class ReadinessRule:
    """描述一条缺失能力的固定扣分规则。"""

    is_missing: Callable[[RepoProfile], bool]
    deduction: int
    finding: Finding
    recommendation: Recommendation


READINESS_RULES = (
    ReadinessRule(
        is_missing=lambda profile: not profile.has_readme,
        deduction=15,
        finding=Finding(
            code="missing_readme",
            severity=Severity.WARNING,
            message="Repository README is missing.",
            evidence=("README.md", "README.rst", "README.txt", "README"),
        ),
        recommendation=Recommendation(
            kind=RecommendationKind.ADD_README,
            title="Add a repository README",
            rationale="Agents need a stable entry point for project context.",
            action="Add a README with project purpose, setup, and verification commands.",
        ),
    ),
    ReadinessRule(
        is_missing=lambda profile: not profile.constraint_files,
        deduction=25,
        finding=Finding(
            code="missing_agent_instructions",
            severity=Severity.WARNING,
            message="Repository-specific agent instructions are missing.",
            evidence=("AGENTS.md", "CLAUDE.md"),
        ),
        recommendation=Recommendation(
            kind=RecommendationKind.ADD_CONSTRAINT_FILE,
            title="Add agent instructions",
            rationale="Agents need repository-specific boundaries and workflows.",
            action="Add AGENTS.md or CLAUDE.md with boundaries and verification commands.",
        ),
    ),
    ReadinessRule(
        is_missing=lambda profile: not profile.test_directories,
        deduction=25,
        finding=Finding(
            code="missing_test_directory",
            severity=Severity.WARNING,
            message="A common test directory was not detected.",
            evidence=("tests", "test", "__tests__", "spec"),
        ),
        recommendation=Recommendation(
            kind=RecommendationKind.ADD_TESTS,
            title="Add an automated test directory",
            rationale="Agents need repeatable checks for behavioral changes.",
            action="Add a conventional test directory and cover core behavior.",
        ),
    ),
    ReadinessRule(
        is_missing=lambda profile: not profile.ci_files,
        deduction=15,
        finding=Finding(
            code="missing_ci_config",
            severity=Severity.WARNING,
            message="A common CI configuration was not detected.",
            evidence=(".github/workflows", ".gitlab-ci.yml", "azure-pipelines.yml"),
        ),
        recommendation=Recommendation(
            kind=RecommendationKind.ADD_CI,
            title="Add continuous integration checks",
            rationale="Automated repository checks reduce unverified agent changes.",
            action="Add CI configuration that runs the repository verification commands.",
        ),
    ),
    ReadinessRule(
        is_missing=lambda profile: not profile.project_markers,
        deduction=10,
        finding=Finding(
            code="missing_project_marker",
            severity=Severity.WARNING,
            message="A supported project marker was not detected.",
            evidence=(
                "pyproject.toml",
                "requirements.txt",
                "package.json",
                "Cargo.toml",
                "go.mod",
            ),
        ),
        recommendation=Recommendation(
            kind=RecommendationKind.REVIEW_TEST_COMMANDS,
            title="Expose the repository project marker",
            rationale="Project markers let AgentOps infer conservative verification commands.",
            action="Add or expose a supported project marker and document test commands.",
        ),
    ),
    ReadinessRule(
        is_missing=lambda profile: not profile.test_commands,
        deduction=10,
        finding=Finding(
            code="missing_test_command",
            severity=Severity.WARNING,
            message="A likely test command could not be inferred.",
            evidence=("project_markers",),
        ),
        recommendation=Recommendation(
            kind=RecommendationKind.REVIEW_TEST_COMMANDS,
            title="Document repository test commands",
            rationale="Agents need a repeatable command to verify changes.",
            action="Document the supported test command in the repository instructions.",
        ),
    ),
)


class ReadinessEvaluator:
    """使用固定规则评估仓库对 AI coding 的支持程度。"""

    def evaluate(self, profile: RepoProfile) -> ReadinessReport:
        """返回带证据和改进建议的 readiness 报告。"""

        matched_rules = tuple(
            rule for rule in READINESS_RULES if rule.is_missing(profile)
        )
        return ReadinessReport(
            profile=profile,
            score=100 - sum(rule.deduction for rule in matched_rules),
            findings=tuple(rule.finding for rule in matched_rules),
            recommendations=tuple(rule.recommendation for rule in matched_rules),
        )
