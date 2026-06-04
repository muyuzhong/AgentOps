"""把 scope-drift 对账结果转换为确定性分数、发现和建议。"""

from __future__ import annotations

from dataclasses import dataclass

from agentops.core.evaluation import Finding, Severity
from agentops.core.recommendation import Recommendation, RecommendationKind
from agentops.evaluators.scope_drift import ScopeDriftFinding, ScopeDriftReport


_DEDUCTIONS = {
    "undeclared_change": 15,
    "declared_not_changed": 10,
    "cross_module_breadth": 10,
}


@dataclass(frozen=True)
class ScopeEvaluation:
    """scope-discipline 的确定性评分结果。"""

    score: int
    findings: tuple[Finding, ...] = ()
    recommendations: tuple[Recommendation, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 友好结构。"""

        return {
            "score": self.score,
            "findings": [finding.to_dict() for finding in self.findings],
            "recommendations": [
                recommendation.to_dict() for recommendation in self.recommendations
            ],
        }


def evaluate_scope(report: ScopeDriftReport) -> ScopeEvaluation:
    """根据确定性 scope findings 评分，跳过需要 LLM 的意图判断。"""

    score = 100
    findings: list[Finding] = []
    recommendations_by_kind: dict[RecommendationKind, Recommendation] = {}

    for finding in report.findings:
        if finding.llm_needed:
            continue
        deduction = _DEDUCTIONS.get(finding.code)
        if deduction is None:
            continue
        score -= deduction
        findings.append(_to_finding(finding))
        recommendation = _to_recommendation(finding)
        recommendations_by_kind.setdefault(recommendation.kind, recommendation)

    return ScopeEvaluation(
        score=max(score, 0),
        findings=tuple(findings),
        recommendations=tuple(recommendations_by_kind.values()),
    )


def _to_finding(finding: ScopeDriftFinding) -> Finding:
    """把探针 finding 转为对外评测 finding。"""

    return Finding(
        code=finding.code,
        severity=Severity.WARNING,
        message=_message_for(finding.code),
        evidence=finding.evidence,
    )


def _to_recommendation(finding: ScopeDriftFinding) -> Recommendation:
    """为每种扣分项生成一条可执行建议。"""

    if finding.code == "undeclared_change":
        return Recommendation(
            kind=RecommendationKind.DECLARE_CHANGED_FILES,
            title="Declare every changed file",
            rationale=(
                "The task report omitted files that appear in git truth, so later "
                "review cannot tell whether the extra changes were intentional."
            ),
            action=(
                "Add every touched path to the task report's Changed Files section "
                "before ending the session."
            ),
        )
    if finding.code == "declared_not_changed":
        return Recommendation(
            kind=RecommendationKind.REVIEW_DECLARED_CHANGES,
            title="Align declared files with git truth",
            rationale=(
                "The task report named files that were not changed, which weakens "
                "the declaration-vs-truth audit trail."
            ),
            action="Remove stale path claims or verify that the intended file was actually changed.",
        )
    return Recommendation(
        kind=RecommendationKind.REVIEW_SCOPE_BOUNDARY,
        title="Review task scope boundaries",
        rationale="The diff spans several top-level modules, which may indicate scope drift.",
        action="Split broad changes into smaller tasks or explain the cross-module coupling.",
    )


def _message_for(code: str) -> str:
    """返回稳定、简短的诊断文案。"""

    if code == "undeclared_change":
        return "Changed a file that the task did not declare."
    if code == "declared_not_changed":
        return "Declared a file that does not appear in the git diff."
    return "Changed files span several top-level modules."
