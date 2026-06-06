"""把 RepoMemory 投影写为人读报告、结构化 JSON 与 skill 候选清单。

写出三种产物，全部**覆盖写出、绝不 append**——记忆是 eval-history.jsonl 的可再生
投影，同样的历史产出字节一致的产物：

- ``agentops-memory.md``：人读记忆——分数/漂移趋势、失败模式（含 N/M 复现 + 热点路径
  + 最近出现）、规则候选、skill 候选；
- ``agentops-memory.json``：镜像 ``RepoMemory.to_dict()`` 的结构化记忆（UTF-8、
  sort_keys、两空格缩进、尾随换行），供 Phase 6 / Studio 消费；
- ``skill-candidates.md``：聚焦、可评审的 skill 候选清单（agent.md 早列为目标产物）。
"""

from __future__ import annotations

import json
from pathlib import Path

from agentops.core.artifact import Artifact, ArtifactKind
from agentops.core.memory import RepoMemory


class MemoryReportWriter:
    """写出仓库记忆产物：覆盖写出，绝不 append（记忆是历史的可再生投影）。"""

    def write(self, memory: RepoMemory, output_dir: Path) -> tuple[Artifact, ...]:
        """创建输出目录，覆盖写出记忆报告、JSON 与 skill 候选清单。"""

        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = output_dir / "agentops-memory.md"
        json_path = output_dir / "agentops-memory.json"
        skills_path = output_dir / "skill-candidates.md"

        markdown_path.write_text(self._render_memory(memory), encoding="utf-8")
        json_path.write_text(
            json.dumps(
                memory.to_dict(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        skills_path.write_text(self._render_skills(memory), encoding="utf-8")

        return (
            Artifact(kind=ArtifactKind.MEMORY_REPORT, path=markdown_path),
            Artifact(kind=ArtifactKind.MEMORY_JSON, path=json_path),
            Artifact(kind=ArtifactKind.SKILL_CANDIDATES, path=skills_path),
        )

    @staticmethod
    def _render_memory(memory: RepoMemory) -> str:
        """渲染顺序稳定的人读记忆报告。"""

        trend = memory.trend
        lines = [
            "# AgentOps Repository Memory",
            "",
            f"Repository: {memory.repo_root}",
            f"Eval samples: {memory.sample_count}",
            "",
            "## Score Trend",
            "",
            f"- Direction: {trend.direction}",
            f"- First score: {MemoryReportWriter._fmt(trend.first_score)}",
            f"- Last score: {MemoryReportWriter._fmt(trend.last_score)}",
            f"- Average score: {MemoryReportWriter._fmt(trend.average_score)}",
            f"- Drift verdicts (cumulative): {trend.drift_verdict_total}",
            "",
            "## Failure Modes",
            "",
        ]
        if memory.failure_modes:
            for mode in memory.failure_modes:
                paths = MemoryReportWriter._format_values(mode.hot_paths)
                lines.append(
                    f"- **{mode.code}**: recurred "
                    f"{mode.occurrence_count}/{mode.sample_count} evals; "
                    f"last seen {mode.last_seen}; hot paths: {paths}"
                )
        else:
            lines.append("- None.")

        lines.extend(["", "## Rule Candidates", ""])
        if memory.rule_candidates:
            for recommendation in memory.rule_candidates:
                lines.append(
                    f"- **{recommendation.title}** ({recommendation.kind.value}): "
                    f"{recommendation.action} Reason: {recommendation.rationale}"
                )
        else:
            lines.append("- None.")

        lines.extend(["", "## Skill Candidates", ""])
        if memory.skill_candidates:
            for skill in memory.skill_candidates:
                evidence = "; ".join(skill.evidence) if skill.evidence else "None"
                lines.append(
                    f"- **{skill.title}** (`{skill.slug}`): {skill.trigger} "
                    f"Rationale: {skill.rationale} Evidence: {evidence}"
                )
        else:
            lines.append("- None.")

        return "\n".join(lines) + "\n"

    @staticmethod
    def _render_skills(memory: RepoMemory) -> str:
        """渲染聚焦、可评审的 skill 候选清单。"""

        lines = [
            "# AgentOps Skill Candidates",
            "",
            f"Derived from {memory.sample_count} eval(s) in {memory.repo_root}.",
            "",
        ]
        if not memory.skill_candidates:
            lines.append("- None.")
            return "\n".join(lines) + "\n"

        for skill in memory.skill_candidates:
            lines.extend(
                [
                    f"## {skill.title}",
                    "",
                    f"- Slug: `{skill.slug}`",
                    f"- Trigger: {skill.trigger}",
                    f"- Rationale: {skill.rationale}",
                    "- Evidence:",
                ]
            )
            for item in skill.evidence:
                lines.append(f"  - {item}")
            lines.append("")

        # 去掉最后一个候选后多余的空行，统一收敛为单个尾随换行。
        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines) + "\n"

    @staticmethod
    def _fmt(value: object) -> str:
        """缺失分数（None）以 n/a 呈现，其余原样。"""

        return "n/a" if value is None else str(value)

    @staticmethod
    def _format_values(values: tuple[str, ...]) -> str:
        """使用统一形式展示零个或多个路径/模块（与 eval 报告一致）。"""

        if not values:
            return "None"
        return ", ".join(f"`{value}`" for value in values)
