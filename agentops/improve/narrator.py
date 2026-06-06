"""资产叙述接缝：把确定性资产草案富化为更可读的建议文本 / 减法诊断。

Phase 6 只提供确定性默认实现（身份变换）。LLM 叙述者留到后续可选切片按同一接口填充，
且**只能改写描述字段**（managed_block 的散文、rationale、trend_summary、Finding.message），
绝不改动结构事实（target / 规则 kind / hook 命令 / 计数 / 证据路径）——与 LLM 意图判官
“绝不重新推导文件集合”、记忆叙述者“绝不改动 code/计数”同构。

接缝先就位、可注入，但本阶段唯一行为是确定性：``DeterministicAssetNarrator`` 直接返回
投影，不改写、不触网、不需 key。后续填充 LLM 叙述者不得改变接缝形状或结构事实。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from agentops.core.asset import ImprovementAssets


@runtime_checkable
class AssetNarrator(Protocol):
    """把确定性改进资产投影富化为更可读描述的可注入接口。"""

    def narrate(self, assets: ImprovementAssets) -> ImprovementAssets:
        """返回（可能富化了描述字段的）资产；结构事实必须保持不变。"""


class DeterministicAssetNarrator:
    """默认叙述者：直接返回确定性模板投影，不改写、不触网、不需 key。"""

    def narrate(self, assets: ImprovementAssets) -> ImprovementAssets:
        """身份变换：原样返回投影。"""

        return assets
