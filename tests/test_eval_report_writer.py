from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agentops.core.eval import (
    SOURCE_DETERMINISTIC,
    SOURCE_LLM,
    VERDICT_DRIFT,
    VERDICT_NEEDS_REVIEW,
    VERDICT_WITHIN_INTENT,
    EvalResult,
    IntentVerdict,
)
from agentops.core.evaluation import Finding, Severity
from agentops.core.recommendation import Recommendation, RecommendationKind
from agentops.writers.eval_report import EvalReportWriter

_TS = datetime(2026, 6, 4, 12, 0, 0, tzinfo=timezone.utc)


def _result(*, score: int = 85, task_title: str = "Fix login") -> EvalResult:
    """构造一个带 findings/recommendations/intent verdict 的评测结果。"""

    return EvalResult(
        repo_root=Path("demo"),
        task_title=task_title,
        declared_paths=("src/auth.py",),
        changed_paths=("src/auth.py", "src/billing.py"),
        score=score,
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
                rationale="Later review cannot tell whether extra changes were intentional.",
                action="Add every touched path to the Changed Files section.",
            ),
        ),
        intent_verdicts=(
            IntentVerdict(
                finding_code="intent_alignment",
                evidence=("scope signal",),
                verdict=VERDICT_NEEDS_REVIEW,
                rationale="Deciding whether it fits the task intent requires review.",
                source=SOURCE_DETERMINISTIC,
            ),
        ),
    )


def test_eval_report_writer_writes_markdown_json_and_history(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"

    artifacts = EvalReportWriter().write(_result(), output_dir, timestamp=_TS)

    assert [artifact.kind.value for artifact in artifacts] == [
        "markdown_report",
        "json_score",
        "eval_history",
    ]
    markdown = (output_dir / "agentops-report.md").read_text(encoding="utf-8")
    assert "# AgentOps Session Eval Report" in markdown
    assert "Fix login" in markdown
    assert "Score: 85/100" in markdown
    # 声明 vs 真相、发现、建议、意图裁决都要在报告里可见。
    assert "src/auth.py" in markdown
    assert "src/billing.py" in markdown
    assert "undeclared_change" in markdown
    assert "Declare every changed file" in markdown
    assert "needs_review" in markdown

    data = json.loads((output_dir / "agentops-score.json").read_text(encoding="utf-8"))
    assert data == _result().to_dict()


def test_eval_report_writer_history_line_carries_timestamp_and_result(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "output"

    EvalReportWriter().write(_result(), output_dir, timestamp=_TS)

    lines = (
        (output_dir / "eval-history.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["timestamp"] == "2026-06-04T12:00:00+00:00"
    assert record["result"] == _result().to_dict()


def test_eval_report_writer_appends_history_preserving_prior_lines(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "output"
    writer = EvalReportWriter()
    later = datetime(2026, 6, 5, 9, 30, 0, tzinfo=timezone.utc)

    writer.write(_result(score=85, task_title="First"), output_dir, timestamp=_TS)
    writer.write(_result(score=70, task_title="Second"), output_dir, timestamp=later)

    lines = (
        (output_dir / "eval-history.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    # 历史是 append-only：每次评测恰好追加一行，旧行保持不变。
    assert len(lines) == 2
    first, second = json.loads(lines[0]), json.loads(lines[1])
    assert first["timestamp"] == "2026-06-04T12:00:00+00:00"
    assert first["result"]["task_title"] == "First"
    assert second["timestamp"] == "2026-06-05T09:30:00+00:00"
    assert second["result"]["task_title"] == "Second"
    # 覆盖式的 markdown/json 反映最近一次评测。
    assert "Second" in (output_dir / "agentops-report.md").read_text(encoding="utf-8")


def test_eval_report_writer_preserves_utf8(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    result = EvalResult(
        repo_root=Path("演示仓库"),
        task_title="修复登录",
        declared_paths=("src/认证.py",),
        changed_paths=("src/认证.py",),
        score=90,
        findings=(
            Finding(
                code="declared_not_changed",
                severity=Severity.WARNING,
                message="声明了一个 diff 中没有出现的文件。",
                evidence=("src/认证.py",),
            ),
        ),
    )

    EvalReportWriter().write(result, output_dir, timestamp=_TS)

    markdown = (output_dir / "agentops-report.md").read_text(encoding="utf-8")
    history = (output_dir / "eval-history.jsonl").read_text(encoding="utf-8")
    assert "修复登录" in markdown
    assert "声明了一个 diff 中没有出现的文件。" in markdown
    assert "演示仓库" in history


def _result_with_llm_verdicts() -> EvalResult:
    """构造一个带 LLM drift + within_intent 两条裁决的评测结果。"""

    return EvalResult(
        repo_root=Path("demo"),
        task_title="Fix login",
        declared_paths=("src/auth.py",),
        changed_paths=("src/auth.py", "src/billing.py", "tests/test_auth.py"),
        score=70,
        intent_verdicts=(
            IntentVerdict(
                finding_code="undeclared_change",
                evidence=("src/billing.py",),
                verdict=VERDICT_DRIFT,
                rationale="billing is unrelated to the login task",
                source=SOURCE_LLM,
            ),
            IntentVerdict(
                finding_code="undeclared_change",
                evidence=("tests/test_auth.py",),
                verdict=VERDICT_WITHIN_INTENT,
                rationale="tests for the auth change",
                source=SOURCE_LLM,
            ),
        ),
    )


def test_llm_verdicts_are_grouped_by_verdict_with_source_labels(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"

    EvalReportWriter().write(_result_with_llm_verdicts(), output_dir, timestamp=_TS)
    markdown = (output_dir / "agentops-report.md").read_text(encoding="utf-8")

    # 按裁决分组，drift 在 within_intent 之前（更值得关注的先列）。
    assert "### drift (1)" in markdown
    assert "### within_intent (1)" in markdown
    assert markdown.index("### drift") < markdown.index("### within_intent")
    # 逐行标注来源，且证据路径可见。
    assert "(llm)" in markdown
    assert "src/billing.py" in markdown
    assert "tests/test_auth.py" in markdown


def test_deterministic_only_report_keeps_flat_phase4_layout(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"

    # _result() 只含一条 needs_review / deterministic 裁决（Phase 4 形态）。
    EvalReportWriter().write(_result(), output_dir, timestamp=_TS)
    markdown = (output_dir / "agentops-report.md").read_text(encoding="utf-8")

    # 仅确定性裁决时不分组：保持 Phase 4 的扁平单行渲染，不出现 ### 分组标题。
    assert "###" not in markdown
    assert (
        "## Intent Verdicts\n\n"
        "- **intent_alignment** (deterministic): needs_review — "
    ) in markdown


def test_history_line_includes_verdict_summary(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"

    EvalReportWriter().write(_result_with_llm_verdicts(), output_dir, timestamp=_TS)
    record = json.loads(
        (output_dir / "eval-history.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )

    # 历史行追加按裁决/来源的计数摘要，供 Phase 5 读 drift 趋势。
    summary = record["verdict_summary"]
    assert summary["total"] == 2
    assert summary["by_verdict"] == {"drift": 1, "within_intent": 1}
    assert summary["by_source"] == {"llm": 2}
    # JSON 评分文件结构不变，仍镜像 EvalResult.to_dict()。
    score_data = json.loads(
        (output_dir / "agentops-score.json").read_text(encoding="utf-8")
    )
    assert score_data == _result_with_llm_verdicts().to_dict()


def test_history_summary_for_empty_verdicts_is_zeroed(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    result = EvalResult(
        repo_root=Path("demo"),
        task_title="Clean",
        declared_paths=("src/auth.py",),
        changed_paths=("src/auth.py",),
        score=100,
    )

    EvalReportWriter().write(result, output_dir, timestamp=_TS)
    record = json.loads(
        (output_dir / "eval-history.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )

    assert record["verdict_summary"] == {
        "total": 0,
        "by_verdict": {},
        "by_source": {},
    }
