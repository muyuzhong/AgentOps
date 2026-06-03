from agentops.core.evidence import ChangedFile, ChangeKind, DiffSummary
from agentops.core.session import TaskReport
from agentops.evaluators.scope_drift import (
    ScopeDriftFinding,
    ScopeDriftReport,
    reconcile_scope,
)


def _diff(*paths: str, kind: ChangeKind = ChangeKind.MODIFIED) -> DiffSummary:
    """用给定路径构造一个最小 DiffSummary（真相）。"""

    files = tuple(
        ChangedFile(path=path, change_kind=kind, additions=1, deletions=0)
        for path in paths
    )
    return DiffSummary(files=files, additions=len(files), deletions=0)


def test_flags_undeclared_change() -> None:
    report = TaskReport(
        title="t",
        goal="g",
        context_used=("src/auth.py",),
        changes=("Adjust auth.",),
    )
    result = reconcile_scope(report, _diff("src/auth.py", "src/billing.py"))

    assert isinstance(result, ScopeDriftReport)
    undeclared = {
        f.evidence for f in result.findings if f.code == "undeclared_change"
    }
    assert ("src/billing.py",) in undeclared
    # 已声明的文件不应被标为未声明改动。
    assert ("src/auth.py",) not in undeclared


def test_flags_declared_not_changed() -> None:
    report = TaskReport(
        title="t",
        goal="g",
        changes=("Update src/auth.py and src/missing.py",),
    )
    result = reconcile_scope(report, _diff("src/auth.py"))

    assert any(
        f.code == "declared_not_changed" and f.evidence == ("src/missing.py",)
        for f in result.findings
    )


def test_flags_cross_module_breadth() -> None:
    report = TaskReport(title="t", goal="g", changes=("broad change",))
    result = reconcile_scope(report, _diff("src/a.py", "tests/b.py", "docs/c.md"))

    breadth = [f for f in result.findings if f.code == "cross_module_breadth"]
    assert breadth
    assert set(breadth[0].evidence) == {"src", "tests", "docs"}


def test_aligned_declaration_has_no_findings() -> None:
    report = TaskReport(
        title="t",
        goal="g",
        context_used=("src/auth.py",),
        changes=("Update src/auth.py",),
    )
    result = reconcile_scope(report, _diff("src/auth.py"))

    assert result.findings == ()


def test_intent_alignment_marks_llm_needed() -> None:
    report = TaskReport(
        title="t",
        goal="g",
        context_used=("src/auth.py",),
        changes=("Adjust auth.",),
    )
    result = reconcile_scope(report, _diff("src/auth.py", "src/billing.py"))

    intent = [f for f in result.findings if f.code == "intent_alignment"]
    assert len(intent) == 1
    assert intent[0].llm_needed is True
    # 确定性发现（文件集合/广度）本身不需要 LLM。
    assert all(
        f.llm_needed is False for f in result.findings if f.code != "intent_alignment"
    )


def test_report_exposes_declared_and_changed_paths() -> None:
    report = TaskReport(title="t", goal="g", context_used=("src/auth.py",))
    result = reconcile_scope(report, _diff("src/auth.py"))

    assert result.changed_paths == ("src/auth.py",)
    assert "src/auth.py" in result.declared_paths


def test_basename_match_avoids_false_undeclared() -> None:
    # 声明里写的是裸文件名，diff 里是带目录的同名文件，不应误报未声明改动。
    report = TaskReport(title="t", goal="g", context_used=("auth.py",))
    result = reconcile_scope(report, _diff("src/auth.py"))

    assert all(f.code != "undeclared_change" for f in result.findings)
    assert result.findings == ()
