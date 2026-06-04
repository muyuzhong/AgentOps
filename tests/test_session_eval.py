from agentops.core.evidence import ChangedFile, ChangeKind, DiffSummary
from agentops.core.session import TaskReport
from agentops.evaluators.scope_drift import reconcile_scope
from agentops.evaluators.session_eval import ScopeEvaluation, evaluate_scope


def _diff(*paths: str, kind: ChangeKind = ChangeKind.MODIFIED) -> DiffSummary:
    """用给定路径构造一个最小 DiffSummary（真相）。"""

    files = tuple(
        ChangedFile(path=path, change_kind=kind, additions=1, deletions=0)
        for path in paths
    )
    return DiffSummary(files=files, additions=len(files), deletions=0)


def test_aligned_task_scores_100_with_no_findings() -> None:
    report = TaskReport(title="t", goal="g", changed_files=("src/auth.py",))
    scope = reconcile_scope(report, _diff("src/auth.py"))

    result = evaluate_scope(scope)

    assert isinstance(result, ScopeEvaluation)
    assert result.score == 100
    assert result.findings == ()
    assert result.recommendations == ()


def test_deducts_per_drift_finding_with_evidence_and_recommendation() -> None:
    report = TaskReport(title="t", goal="g", changed_files=("src/auth.py",))
    scope = reconcile_scope(report, _diff("src/auth.py", "src/billing.py"))

    result = evaluate_scope(scope)

    # 未声明改动应成为一条带文件证据的诊断发现。
    undeclared = [f for f in result.findings if f.code == "undeclared_change"]
    assert undeclared
    assert undeclared[0].evidence == ("src/billing.py",)
    # 每次扣分都必须伴随可执行的改进建议。
    assert result.recommendations
    assert result.score < 100


def test_intent_alignment_is_not_scored_deterministically() -> None:
    # intent_alignment 是 LLM 接缝，不应进入确定性 findings，也不参与扣分。
    report = TaskReport(title="t", goal="g", changed_files=("src/auth.py",))
    scope = reconcile_scope(report, _diff("src/auth.py", "src/billing.py"))

    result = evaluate_scope(scope)

    assert any(f.code == "intent_alignment" for f in scope.findings)
    assert all(f.code != "intent_alignment" for f in result.findings)


def test_score_floors_at_zero() -> None:
    # 大量未声明改动应把分数压到下限 0，而不是负数。
    report = TaskReport(title="t", goal="g", changed_files=("declared.py",))
    many = tuple(f"src/file{index}.py" for index in range(10))
    scope = reconcile_scope(report, _diff("declared.py", *many))

    result = evaluate_scope(scope)

    assert result.score == 0


def test_deduplicates_recommendations_by_kind() -> None:
    # 多个 undeclared_change 只产出一条"声明改动文件"的建议，避免重复刷屏。
    report = TaskReport(title="t", goal="g", changed_files=("src/auth.py",))
    scope = reconcile_scope(report, _diff("src/auth.py", "src/b.py", "src/c.py"))

    result = evaluate_scope(scope)

    declare = [
        r
        for r in result.recommendations
        if r.kind.value == "declare_changed_files"
    ]
    assert len(declare) == 1
