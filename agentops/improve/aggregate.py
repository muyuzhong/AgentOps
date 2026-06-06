"""把 RepoMemory + 现有指令文件装配为 ImprovementAssets 投影（确定性，叙述接缝可注入）。

build_improvement_assets 是改进资产的装配点：顺序调用各确定性投影——趋势一句话摘要、
指令文件加法/减法建议、hook 提案、透传 skill 候选、推荐运行节奏——组成一个
``ImprovementAssets``，再交给可注入的 ``AssetNarrator`` 做描述富化。默认叙述者是确定性
身份实现：同样的 (memory, instructions, readme) 产出字节一致的资产，不触网、不需 key。
叙述者只能改写描述字段，绝不改动结构事实（target / 规则 kind / hook 命令 / 计数 / 路径）。
"""

from __future__ import annotations

from agentops.core.asset import ImprovementAssets
from agentops.core.memory import RepoMemory, ScoreTrend
from agentops.improve.hooks import derive_hook_proposals
from agentops.improve.instructions import derive_instruction_suggestions
from agentops.improve.narrator import AssetNarrator, DeterministicAssetNarrator

# 推荐运行节奏（确定性）：把 observe→evaluate→diagnose→improve 闭环落到具体命令上。
_WORKFLOW_STEPS: tuple[str, ...] = (
    "Run `agentops eval --repo .` after each task to capture scope-discipline ground truth.",
    "Run `agentops memory --repo .` to refresh distilled failure modes as history accumulates.",
    "Run `agentops suggest --repo .` to regenerate adoptable CLAUDE.md / AGENTS.md / hook "
    "assets when the trend worsens or new failure modes appear.",
)


def build_improvement_assets(
    memory: RepoMemory,
    *,
    repo_root: str,
    instructions: dict[str, str | None],
    readme: str | None = None,
    narrator: AssetNarrator | None = None,
) -> ImprovementAssets:
    """把 RepoMemory + 现有指令文件确定性地投影为可采纳的改进资产；narrator 默认身份实现。"""

    assets = ImprovementAssets(
        repo_root=repo_root,
        sample_count=memory.sample_count,
        trend_summary=_trend_summary(memory.trend),
        instruction_suggestions=derive_instruction_suggestions(
            memory, instructions, readme
        ),
        hook_proposals=derive_hook_proposals(memory.failure_modes),
        # skill 候选透传：writer 据此渲染 skill 脚手架。
        skill_candidates=memory.skill_candidates,
        workflow_steps=_WORKFLOW_STEPS,
    )

    # 默认走确定性身份叙述者：投影原样返回，不触网、不需 key。
    chosen = narrator if narrator is not None else DeterministicAssetNarrator()
    return chosen.narrate(assets)


def _trend_summary(trend: ScoreTrend) -> str:
    """把 ScoreTrend 投影为一句话确定性摘要（None 分数以 n/a 呈现）。"""

    first = "n/a" if trend.first_score is None else str(trend.first_score)
    last = "n/a" if trend.last_score is None else str(trend.last_score)
    return (
        f"Scope-discipline trend is {trend.direction} over {trend.sample_count} eval(s) "
        f"({first}->{last}); {trend.drift_verdict_total} drift verdict(s)."
    )
