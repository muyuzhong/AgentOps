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
from agentops.core.eval import EvalResult


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
        history_record = {
            "timestamp": timestamp.isoformat(),
            "result": result.to_dict(),
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
        if result.intent_verdicts:
            for verdict in result.intent_verdicts:
                evidence = EvalReportWriter._format_values(verdict.evidence)
                lines.append(
                    f"- **{verdict.finding_code}** ({verdict.source}): "
                    f"{verdict.verdict} — {verdict.rationale} Evidence: {evidence}"
                )
        else:
            lines.append("- None.")

        return "\n".join(lines) + "\n"

    @staticmethod
    def _format_values(values: tuple[str, ...]) -> str:
        """使用统一形式展示零个或多个路径/证据。"""

        if not values:
            return "None"
        return ", ".join(f"`{value}`" for value in values)
