"""把累积记忆 + 现有指令文件确定性投影为可采纳改进资产的模块。

本阶段全部投影都是确定性的：加法复用规则候选，减法只做可辩护的结构诊断，hook 提案按
失败模式映射到现有命令，并在一个可注入的 AssetNarrator 接缝后装配为 ImprovementAssets。
默认叙述者只有确定性身份实现：同样输入产出字节一致的资产，不触网、不需 key、无新增依赖。
"""

from agentops.improve.aggregate import build_improvement_assets
from agentops.improve.hooks import derive_hook_proposals
from agentops.improve.instructions import (
    INSTRUCTION_LINE_BUDGET,
    REPO_RULES_BLOCK_END,
    REPO_RULES_BLOCK_START,
    derive_instruction_suggestions,
)
from agentops.improve.narrator import AssetNarrator, DeterministicAssetNarrator

__all__ = [
    "AssetNarrator",
    "DeterministicAssetNarrator",
    "INSTRUCTION_LINE_BUDGET",
    "REPO_RULES_BLOCK_END",
    "REPO_RULES_BLOCK_START",
    "build_improvement_assets",
    "derive_hook_proposals",
    "derive_instruction_suggestions",
]
