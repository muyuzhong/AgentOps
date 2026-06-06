"""Phase 6 改进资产的核心数据模型。

把 RepoMemory + 现有指令文件确定性地投影为可采纳的改进资产时，需要三个小包装模型：
对单个指令文件的改进建议（InstructionSuggestion：加法 + 减法 + 可采纳托管块）、一条
hook 提案（HookProposal），以及总产物（ImprovementAssets）。它们复用既有的
Recommendation / Finding / SkillCandidate，不另立平行的候选体系。

这些模型只是投影载体：同样的输入产出字节一致的资产。模型本身不计算、不读盘、不触网，
派生由 agentops/improve/ 下的确定性函数负责，叙述富化由 AssetNarrator 接缝负责——它只能
改写描述字段，绝不改动这里记录的结构事实（target / 规则 kind / hook 命令 / 计数 / 证据路径）。
"""

from __future__ import annotations

from dataclasses import dataclass

from agentops.core.evaluation import Finding
from agentops.core.memory import SkillCandidate
from agentops.core.recommendation import Recommendation


@dataclass(frozen=True)
class InstructionSuggestion:
    """对一个指令文件（CLAUDE.md / AGENTS.md）的改进建议：加法 + 减法 + 可采纳托管块。"""

    target: str  # "CLAUDE.md" | "AGENTS.md"
    exists: bool  # 目标文件当前是否存在（不存在 → 纯加法 + “建议新建”）
    line_count: int | None  # 现有文件行数（不存在时 None）
    additions: tuple[Recommendation, ...]  # 该加什么：复用规则候选；文件缺失时追加 ADD_CONSTRAINT_FILE
    subtractions: tuple[Finding, ...]  # 该精简什么：确定性结构诊断（超长 / 重复 README）
    managed_block: str  # 可直接采纳的 agentops:repo-rules 托管块文本（含 marker；无规则时为空串）

    def to_dict(self) -> dict[str, object]:
        """转换为 writer 可直接写出的稳定结构（tuple 转 list、None 原样保留）。"""

        return {
            "target": self.target,
            "exists": self.exists,
            "line_count": self.line_count,
            "additions": [recommendation.to_dict() for recommendation in self.additions],
            "subtractions": [finding.to_dict() for finding in self.subtractions],
            "managed_block": self.managed_block,
        }


@dataclass(frozen=True)
class HookProposal:
    """一条 hook 提案：针对某个反复失败模式，建议装哪个 hook、跑什么 agentops 命令。"""

    slug: str  # 稳定 id，如 check-session-log-stop-hook
    failure_codes: tuple[str, ...]  # 触发该提案的失败模式 code（去重合并后可能含多个）
    event: str  # Claude Code hook 事件，如 "Stop"
    title: str
    rationale: str  # 为什么：N/M 复现 + 该 hook 如何拦截（确定性模板）
    command: str  # hook 运行的现有 agentops 命令
    settings_snippet: str  # 可直接采纳的 settings.json 片段（确定性渲染）
    evidence: tuple[str, ...]  # N/M + 热点路径

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 友好结构（tuple 转 list）。"""

        return {
            "slug": self.slug,
            "failure_codes": list(self.failure_codes),
            "event": self.event,
            "title": self.title,
            "rationale": self.rationale,
            "command": self.command,
            "settings_snippet": self.settings_snippet,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class ImprovementAssets:
    """Phase 6 总产物：RepoMemory + 现有指令文件 → 可采纳的改进资产（确定性投影）。"""

    repo_root: str
    sample_count: int
    trend_summary: str  # 趋势的一句话确定性摘要
    instruction_suggestions: tuple[InstructionSuggestion, ...]  # CLAUDE.md、AGENTS.md（固定顺序）
    hook_proposals: tuple[HookProposal, ...]
    skill_candidates: tuple[SkillCandidate, ...]  # 透传 memory 的 skill 候选 → skill 脚手架
    workflow_steps: tuple[str, ...]  # 推荐运行节奏（确定性）

    def to_dict(self) -> dict[str, object]:
        """递归转换为 writer 可直接写出的稳定结构（每层模型自行序列化）。"""

        return {
            "repo_root": self.repo_root,
            "sample_count": self.sample_count,
            "trend_summary": self.trend_summary,
            "instruction_suggestions": [
                suggestion.to_dict() for suggestion in self.instruction_suggestions
            ],
            "hook_proposals": [proposal.to_dict() for proposal in self.hook_proposals],
            "skill_candidates": [
                candidate.to_dict() for candidate in self.skill_candidates
            ],
            "workflow_steps": list(self.workflow_steps),
        }
