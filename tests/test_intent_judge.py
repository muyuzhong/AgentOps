from agentops.core.eval import IntentVerdict
from agentops.core.evidence import ChangedFile, ChangeKind, DiffSummary
from agentops.core.session import TaskReport
from agentops.evaluators.scope_drift import (
    ScopeDriftFinding,
    ScopeDriftReport,
    reconcile_scope,
)
from agentops.judges.intent import DeterministicIntentJudge, IntentJudge


def _diff(*paths: str) -> DiffSummary:
    """用给定路径构造一个最小 DiffSummary（真相）。"""

    files = tuple(
        ChangedFile(path=path, change_kind=ChangeKind.MODIFIED, additions=1, deletions=0)
        for path in paths
    )
    return DiffSummary(files=files, additions=len(files), deletions=0)


def test_deterministic_judge_marks_intent_alignment_needs_review() -> None:
    report = TaskReport(title="t", goal="g", changed_files=("src/auth.py",))
    scope = reconcile_scope(report, _diff("src/auth.py", "src/billing.py"))

    verdicts = DeterministicIntentJudge().judge(report, scope)

    intent = [v for v in verdicts if v.finding_code == "intent_alignment"]
    assert len(intent) == 1
    assert intent[0].verdict == "needs_review"
    assert intent[0].source == "deterministic"


def test_deterministic_judge_returns_no_verdicts_without_llm_findings() -> None:
    # 对账无漂移时没有 intent_alignment，判官返回空裁决。
    report = TaskReport(title="t", goal="g", changed_files=("src/auth.py",))
    scope = reconcile_scope(report, _diff("src/auth.py"))

    verdicts = DeterministicIntentJudge().judge(report, scope)

    assert verdicts == ()


def test_deterministic_judge_only_judges_llm_needed_findings() -> None:
    # 手工构造：一条确定性发现 + 一条标记 llm_needed 的发现。
    scope = ScopeDriftReport(
        declared_paths=("a.py",),
        changed_paths=("a.py", "b.py"),
        findings=(
            ScopeDriftFinding(
                code="undeclared_change", evidence=("b.py",), llm_needed=False
            ),
            ScopeDriftFinding(
                code="intent_alignment", evidence=("signal",), llm_needed=True
            ),
        ),
    )

    verdicts = DeterministicIntentJudge().judge(TaskReport(title="t", goal="g"), scope)

    # 只对 llm_needed=True 的发现产出裁决。
    assert len(verdicts) == 1
    assert verdicts[0].finding_code == "intent_alignment"
    assert all(isinstance(v, IntentVerdict) for v in verdicts)


def test_deterministic_judge_ignores_non_intent_llm_needed_findings() -> None:
    scope = ScopeDriftReport(
        declared_paths=("a.py",),
        changed_paths=("a.py", "b.py"),
        findings=(
            ScopeDriftFinding(
                code="other_dimension", evidence=("signal",), llm_needed=True
            ),
        ),
    )

    verdicts = DeterministicIntentJudge().judge(TaskReport(title="t", goal="g"), scope)

    assert verdicts == ()


def test_deterministic_judge_satisfies_intent_judge_protocol() -> None:
    # DeterministicIntentJudge 必须满足可注入的 IntentJudge 协议。
    assert isinstance(DeterministicIntentJudge(), IntentJudge)
