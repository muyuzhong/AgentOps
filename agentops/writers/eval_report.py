"""将会话评测结果写为报告、评分和可累积的历史产物。

写出三种产物：
- ``agentops-report.md``：人读的评测报告（声明 vs 真相、发现、建议、意图裁决）；
- ``agentops-score.json``：与 ``EvalResult.to_dict()`` 一致的结构化评分；
- ``eval-history.jsonl``：append-only 历史，每次评测追加一行带时间戳的记录，
  供后续（Phase 5）做趋势分析。markdown 和 json 覆盖写出、历史只追加。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from agentops.core.artifact import Artifact, ArtifactKind
from agentops.core.eval import (
    SOURCE_LLM,
    VERDICT_DRIFT,
    VERDICT_NEEDS_REVIEW,
    VERDICT_WITHIN_INTENT,
    EvalResult,
    IntentVerdict,
)

# 报告里裁决分组的展示顺序：更值得关注的先列。
_VERDICT_ORDER = (VERDICT_DRIFT, VERDICT_WITHIN_INTENT, VERDICT_NEEDS_REVIEW)


class EvalReportWriter:
    """写出稳定的评测报告、评分文件，并向历史追加一行。"""

    def write(
        self,
        result: EvalResult,
        output_dir: Path,
        *,
        timestamp: datetime,
    ) -> tuple[Artifact, ...]:
        """创建输出目录，覆盖写报告与评分，并向历史追加一条记录。"""

        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = output_dir / "agentops-report.md"
        json_path = output_dir / "agentops-score.json"
        history_path = output_dir / "eval-history.jsonl"

        markdown_path.write_text(self._render_markdown(result), encoding="utf-8")
        json_path.write_text(
            json.dumps(
                result.to_dict(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        # 历史是 append-only：保留全部历史行，只为本次评测追加一条带时间戳的记录。
        # 额外附上按裁决/来源的计数摘要，供 Phase 5 读取 drift 趋势。
        history_record = {
            "timestamp": timestamp.isoformat(),
            "result": result.to_dict(),
            "verdict_summary": self._verdict_summary(result.intent_verdicts),
        }
        with history_path.open("a", encoding="utf-8") as history_file:
            history_file.write(
                json.dumps(history_record, ensure_ascii=False, sort_keys=True) + "\n"
            )

        return (
            Artifact(kind=ArtifactKind.MARKDOWN_REPORT, path=markdown_path),
            Artifact(kind=ArtifactKind.JSON_SCORE, path=json_path),
            Artifact(kind=ArtifactKind.EVAL_HISTORY, path=history_path),
        )

    @staticmethod
    def _render_markdown(result: EvalResult) -> str:
        """将评测结果渲染为可读且顺序稳定的 Markdown。"""

        lines = [
            "# AgentOps Session Eval Report",
            "",
            f"Task: {result.task_title}",
            f"Score: {result.score}/100",
            "",
            "## Declared vs Changed",
            "",
            f"- Declared paths: {EvalReportWriter._format_values(result.declared_paths)}",
            f"- Changed paths: {EvalReportWriter._format_values(result.changed_paths)}",
            "",
            "## Findings",
            "",
        ]
        if result.findings:
            for finding in result.findings:
                evidence = EvalReportWriter._format_values(finding.evidence)
                lines.append(
                    f"- **{finding.code}** ({finding.severity.value}): "
                    f"{finding.message} Evidence: {evidence}"
                )
        else:
            lines.append("- None.")

        lines.extend(["", "## Recommendations", ""])
        if result.recommendations:
            for recommendation in result.recommendations:
                lines.append(
                    f"- **{recommendation.title}**: {recommendation.action} "
                    f"Reason: {recommendation.rationale}"
                )
        else:
            lines.append("- None.")

        lines.extend(["", "## Intent Verdicts", ""])
        lines.extend(EvalReportWriter._render_verdicts(result.intent_verdicts))

        return "\n".join(lines) + "\n"

    @staticmethod
    def _render_verdicts(verdicts: tuple[IntentVerdict, ...]) -> list[str]:
        """渲染意图裁决：仅确定性时保持 Phase 4 扁平形态，含 LLM 富化时按裁决分组。"""

        if not verdicts:
            return ["- None."]
        # 仅确定性裁决（默认路径）：保持 Phase 4 的扁平单行渲染，逐字不变。
        if not any(verdict.source == SOURCE_LLM for verdict in verdicts):
            return [EvalReportWriter._flat_verdict_line(verdict) for verdict in verdicts]

        # 含 LLM 裁决：按裁决分组（drift → within_intent → needs_review），逐行标注来源。
        blocks: list[list[str]] = []
        for value in _VERDICT_ORDER:
            group = [verdict for verdict in verdicts if verdict.verdict == value]
            if not group:
                continue
            block = [f"### {value} ({len(group)})", ""]
            block.extend(
                EvalReportWriter._grouped_verdict_line(verdict) for verdict in group
            )
            blocks.append(block)

        rendered: list[str] = []
        for index, block in enumerate(blocks):
            if index:
                rendered.append("")  # 组间空行
            rendered.extend(block)
        return rendered

    @staticmethod
    def _flat_verdict_line(verdict: IntentVerdict) -> str:
        """Phase 4 形态的扁平裁决行（裁决取值内联在行内）。"""

        evidence = EvalReportWriter._format_values(verdict.evidence)
        return (
            f"- **{verdict.finding_code}** ({verdict.source}): "
            f"{verdict.verdict} — {verdict.rationale} Evidence: {evidence}"
        )

    @staticmethod
    def _grouped_verdict_line(verdict: IntentVerdict) -> str:
        """分组形态的裁决行（裁决取值已在分组标题里，行内省略）。"""

        evidence = EvalReportWriter._format_values(verdict.evidence)
        return (
            f"- **{verdict.finding_code}** ({verdict.source}): "
            f"{verdict.rationale} Evidence: {evidence}"
        )

    @staticmethod
    def _verdict_summary(verdicts: tuple[IntentVerdict, ...]) -> dict[str, object]:
        """按裁决与来源汇总计数，写入历史行供后续趋势分析。"""

        by_verdict: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for verdict in verdicts:
            by_verdict[verdict.verdict] = by_verdict.get(verdict.verdict, 0) + 1
            by_source[verdict.source] = by_source.get(verdict.source, 0) + 1
        return {
            "total": len(verdicts),
            "by_verdict": dict(sorted(by_verdict.items())),
            "by_source": dict(sorted(by_source.items())),
        }

    @staticmethod
    def _format_values(values: tuple[str, ...]) -> str:
        """使用统一形式展示零个或多个路径/证据。"""

        if not values:
            return "None"
        return ", ".join(f"`{value}`" for value in values)
