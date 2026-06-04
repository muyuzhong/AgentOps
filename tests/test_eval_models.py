from pathlib import Path

import pytest

import agentops.core as core
from agentops.core.eval import (
    SOURCE_DETERMINISTIC,
    VERDICT_NEEDS_REVIEW,
    EvalResult,
    IntentVerdict,
)
from agentops.core.evaluation import Finding, Severity
from agentops.core.recommendation import Recommendation, RecommendationKind


def test_intent_verdict_serializes_stably() -> None:
    verdict = IntentVerdict(
        finding_code="intent_alignment",
        evidence=("signal",),
        verdict=VERDICT_NEEDS_REVIEW,
        rationale="needs review",
        source=SOURCE_DETERMINISTIC,
    )

    assert verdict.to_dict() == {
        "finding_code": "intent_alignment",
        "evidence": ["signal"],
        "verdict": "needs_review",
        "rationale": "needs review",
        "source": "deterministic",
    }


def test_intent_verdict_rejects_invalid_verdict_or_source() -> None:
    with pytest.raises(ValueError, match="invalid intent verdict"):
        IntentVerdict("c", (), "bogus", "r", SOURCE_DETERMINISTIC)
    with pytest.raises(ValueError, match="invalid intent verdict source"):
        IntentVerdict("c", (), VERDICT_NEEDS_REVIEW, "r", "bogus")


def test_eval_result_serializes_stably(tmp_path: Path) -> None:
    result = EvalResult(
        repo_root=tmp_path,
        task_title="Fix login",
        declared_paths=("src/auth.py",),
        changed_paths=("src/auth.py", "src/billing.py"),
        score=85,
        findings=(
            Finding(
                code="undeclared_change",
                severity=Severity.WARNING,
                message="Changed a file that the task did not declare.",
                evidence=("src/billing.py",),
            ),
        ),
        recommendations=(
            Recommendation(
                kind=RecommendationKind.DECLARE_CHANGED_FILES,
                title="Declare every changed file",
                rationale="r",
                action="a",
            ),
        ),
        intent_verdicts=(
            IntentVerdict(
                finding_code="intent_alignment",
                evidence=("signal",),
                verdict=VERDICT_NEEDS_REVIEW,
                rationale="needs review",
                source=SOURCE_DETERMINISTIC,
            ),
        ),
    )

    assert result.to_dict() == {
        "repo_root": str(tmp_path),
        "task_title": "Fix login",
        "declared_paths": ["src/auth.py"],
        "changed_paths": ["src/auth.py", "src/billing.py"],
        "score": 85,
        "findings": [
            {
                "code": "undeclared_change",
                "severity": "warning",
                "message": "Changed a file that the task did not declare.",
                "evidence": ["src/billing.py"],
            }
        ],
        "recommendations": [
            {
                "kind": "declare_changed_files",
                "title": "Declare every changed file",
                "rationale": "r",
                "action": "a",
            }
        ],
        "intent_verdicts": [
            {
                "finding_code": "intent_alignment",
                "evidence": ["signal"],
                "verdict": "needs_review",
                "rationale": "needs review",
                "source": "deterministic",
            }
        ],
    }


def test_eval_result_defaults_are_empty(tmp_path: Path) -> None:
    result = EvalResult(
        repo_root=tmp_path,
        task_title="t",
        declared_paths=(),
        changed_paths=(),
        score=100,
    )

    assert result.findings == ()
    assert result.recommendations == ()
    assert result.intent_verdicts == ()


def test_eval_result_rejects_out_of_range_score(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="score must be between 0 and 100"):
        EvalResult(
            repo_root=tmp_path,
            task_title="t",
            declared_paths=(),
            changed_paths=(),
            score=101,
        )


def test_core_exports_eval_types() -> None:
    assert core.EvalResult is EvalResult
    assert core.IntentVerdict is IntentVerdict
