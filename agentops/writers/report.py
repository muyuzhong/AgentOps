"""将 readiness 报告写为面向开发者和工具链的产物。"""

from __future__ import annotations

import json
from pathlib import Path

from agentops.core.artifact import Artifact, ArtifactKind
from agentops.core.evaluation import ReadinessReport


class ReportWriter:
    """写出稳定的 Markdown 报告和 JSON 评分文件。"""

    def write(
        self, report: ReadinessReport, output_dir: Path
    ) -> tuple[Artifact, ...]:
        """创建输出目录并按固定顺序写出两种产物。"""

        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = output_dir / "agentops-report.md"
        json_path = output_dir / "agentops-score.json"

        markdown_path.write_text(self._render_markdown(report), encoding="utf-8")
        json_path.write_text(
            json.dumps(
                report.to_dict(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        return (
            Artifact(kind=ArtifactKind.MARKDOWN_REPORT, path=markdown_path),
            Artifact(kind=ArtifactKind.JSON_SCORE, path=json_path),
        )

    @staticmethod
    def _render_markdown(report: ReadinessReport) -> str:
        """将领域模型渲染为可读且顺序稳定的 Markdown。"""

        profile = report.profile
        lines = [
            "# AgentOps Repository Readiness Report",
            "",
            f"Score: {report.score}/100",
            "",
            "## Repository Facts",
            "",
            f"- Root: `{profile.root}`",
            f"- README detected: `{profile.has_readme}`",
            f"- Constraint files: {ReportWriter._format_values(profile.constraint_files)}",
            f"- Test directories: {ReportWriter._format_values(profile.test_directories)}",
            f"- CI files: {ReportWriter._format_values(profile.ci_files)}",
            f"- Project markers: {ReportWriter._format_values(profile.project_markers)}",
            f"- Test commands: {ReportWriter._format_values(profile.test_commands)}",
            "",
            "## Findings",
            "",
        ]
        if report.findings:
            for finding in report.findings:
                evidence = ReportWriter._format_values(finding.evidence)
                lines.append(
                    f"- **{finding.code}** ({finding.severity.value}): "
                    f"{finding.message} Evidence: {evidence}"
                )
        else:
            lines.append("- None.")

        lines.extend(["", "## Recommendations", ""])
        if report.recommendations:
            for recommendation in report.recommendations:
                lines.append(
                    f"- **{recommendation.title}**: {recommendation.action} "
                    f"Reason: {recommendation.rationale}"
                )
        else:
            lines.append("- None.")

        return "\n".join(lines) + "\n"

    @staticmethod
    def _format_values(values: tuple[str, ...]) -> str:
        """使用统一形式展示零个或多个仓库事实。"""

        if not values:
            return "None"
        return ", ".join(f"`{value}`" for value in values)
