"""把 ImprovementAssets 投影写为可评审、可直接采纳的改进资产产物。

写出四种产物，全部覆盖写出、绝不 append——资产是 eval-history.jsonl + 现有指令文件的
可再生投影，同样输入产出字节一致的产物：

- ``suggested-claude-md.md`` / ``suggested-agents-md.md``：针对各指令文件的可采纳
  agentops:repo-rules 托管块（加法，放进围栏代码块以便直接粘贴）+ 确定性减法诊断 +
  文件缺失提示；
- ``suggested-hooks.md``：每个反复失败模式一条 hook 提案 + settings.json 片段 +
  工作流指引 + skill 脚手架；
- ``agentops-suggestions.json``：镜像 ImprovementAssets.to_dict()（UTF-8、sort_keys、
  两空格缩进、尾随换行），供 Studio / Phase 7 消费。

沿用 MemoryReportWriter 的约定：确定性顺序、None 以 ``n/a`` 呈现、路径/取值用反引号包裹、
单个尾随换行。MemoryReportWriter 不在 writers/__init__.py 中再导出，本写入器同样按需直接导入。
"""

from __future__ import annotations

import json
from pathlib import Path

from agentops.core.artifact import Artifact, ArtifactKind
from agentops.core.asset import ImprovementAssets, InstructionSuggestion


class ImprovementReportWriter:
    """写出改进资产产物：覆盖写出，绝不 append（资产是记忆 + 指令文件的可再生投影）。"""

    def write(self, assets: ImprovementAssets, output_dir: Path) -> tuple[Artifact, ...]:
        """创建输出目录，覆盖写出两份指令建议、hook 提案与结构化 JSON。"""

        output_dir.mkdir(parents=True, exist_ok=True)
        claude_path = output_dir / "suggested-claude-md.md"
        agents_path = output_dir / "suggested-agents-md.md"
        hooks_path = output_dir / "suggested-hooks.md"
        json_path = output_dir / "agentops-suggestions.json"

        claude_path.write_text(
            self._render_instruction(assets, "CLAUDE.md"), encoding="utf-8"
        )
        agents_path.write_text(
            self._render_instruction(assets, "AGENTS.md"), encoding="utf-8"
        )
        hooks_path.write_text(self._render_hooks(assets), encoding="utf-8")
        json_path.write_text(
            json.dumps(
                assets.to_dict(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        return (
            Artifact(kind=ArtifactKind.SUGGESTED_CLAUDE_MD, path=claude_path),
            Artifact(kind=ArtifactKind.SUGGESTED_AGENTS_MD, path=agents_path),
            Artifact(kind=ArtifactKind.HOOK_PROPOSALS, path=hooks_path),
            Artifact(kind=ArtifactKind.SUGGESTIONS_JSON, path=json_path),
        )

    @staticmethod
    def _find_suggestion(
        assets: ImprovementAssets, target: str
    ) -> InstructionSuggestion | None:
        """按 target 定位指令建议（CLAUDE.md / AGENTS.md）。"""

        for suggestion in assets.instruction_suggestions:
            if suggestion.target == target:
                return suggestion
        return None

    @classmethod
    def _render_instruction(cls, assets: ImprovementAssets, target: str) -> str:
        """渲染单个指令文件的加法托管块 + 减法诊断 + 缺失提示。"""

        suggestion = cls._find_suggestion(assets, target)
        lines = [
            f"# AgentOps Suggested {target}",
            "",
            f"Repository: {assets.repo_root}",
            f"Eval samples: {assets.sample_count}",
            "",
        ]
        if suggestion is None:
            lines.append(f"No suggestion projected for {target}.")
            return "\n".join(lines) + "\n"

        lines.extend(
            [
                f"- Exists: {'yes' if suggestion.exists else 'no'}",
                f"- Line count: {cls._fmt(suggestion.line_count)}",
                f"- Additions: {len(suggestion.additions)}",
                "",
            ]
        )
        if not suggestion.exists:
            lines.extend(
                [
                    f"> `{target}` is missing — create it and paste the managed block below.",
                    "",
                ]
            )

        lines.extend(["## What to Add (加法)", ""])
        if suggestion.managed_block:
            lines.extend(
                [
                    "Paste this AgentOps-managed block; it carries one rule per recurring "
                    "failure mode:",
                    "",
                    "```markdown",
                    suggestion.managed_block,
                    "```",
                    "",
                ]
            )
        else:
            lines.extend(["No recurring rules distilled yet.", ""])

        if suggestion.additions:
            for recommendation in suggestion.additions:
                lines.append(
                    f"- **{recommendation.title}** ({recommendation.kind.value}): "
                    f"{recommendation.action} Reason: {recommendation.rationale}"
                )
            lines.append("")

        lines.extend(["## What to Trim (减法)", ""])
        if suggestion.subtractions:
            for finding in suggestion.subtractions:
                evidence = cls._format_values(finding.evidence)
                lines.append(
                    f"- **{finding.severity.value}** {finding.code}: "
                    f"{finding.message} (evidence: {evidence})"
                )
        else:
            lines.append("- None.")

        return "\n".join(lines) + "\n"

    @classmethod
    def _render_hooks(cls, assets: ImprovementAssets) -> str:
        """渲染 hook 提案 + settings.json 片段 + 工作流指引 + skill 脚手架。"""

        lines = [
            "# AgentOps Suggested Hooks & Workflow",
            "",
            f"Repository: {assets.repo_root}",
            f"Eval samples: {assets.sample_count}",
            "",
            "## Hook Proposals",
            "",
        ]
        if assets.hook_proposals:
            for proposal in assets.hook_proposals:
                lines.extend(
                    [
                        f"### {proposal.title}",
                        "",
                        f"- Slug: `{proposal.slug}`",
                        f"- Event: {proposal.event}",
                        f"- Command: `{proposal.command}`",
                        f"- Failure codes: {cls._format_values(proposal.failure_codes)}",
                        f"- Rationale: {proposal.rationale}",
                        f"- Evidence: {cls._format_values(proposal.evidence)}",
                        "",
                        "```json",
                        proposal.settings_snippet,
                        "```",
                        "",
                    ]
                )
        else:
            lines.extend(["- None.", ""])

        lines.extend(["## Workflow Guidance", "", f"- Trend: {assets.trend_summary}"])
        for step in assets.workflow_steps:
            lines.append(f"- {step}")
        lines.append("")

        lines.extend(["## Skill Scaffolds", ""])
        if assets.skill_candidates:
            for skill in assets.skill_candidates:
                evidence = "; ".join(skill.evidence) if skill.evidence else "None"
                lines.extend(
                    [
                        f"### {skill.title}",
                        "",
                        f"- Slug: `{skill.slug}`",
                        f"- Trigger: {skill.trigger}",
                        f"- Rationale: {skill.rationale}",
                        f"- Evidence: {evidence}",
                        "",
                    ]
                )
        else:
            lines.extend(["- None.", ""])

        # 收敛尾随空行为单个换行（与 MemoryReportWriter 的 skill 清单一致）。
        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines) + "\n"

    @staticmethod
    def _fmt(value: object) -> str:
        """缺失值（None）以 n/a 呈现，其余原样。"""

        return "n/a" if value is None else str(value)

    @staticmethod
    def _format_values(values: tuple[str, ...]) -> str:
        """使用统一形式展示零个或多个取值（与记忆/评测报告一致）。"""

        if not values:
            return "None"
        return ", ".join(f"`{value}`" for value in values)
