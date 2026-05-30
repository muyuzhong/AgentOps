"""仓库改进建议数据模型。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RecommendationKind(str, Enum):
    """第一阶段支持的确定性改进建议类型。"""

    ADD_CONSTRAINT_FILE = "add_constraint_file"
    ADD_README = "add_readme"
    ADD_TESTS = "add_tests"
    ADD_CI = "add_ci"
    REVIEW_TEST_COMMANDS = "review_test_commands"


@dataclass(frozen=True)
class Recommendation:
    """保存一条可以直接执行的仓库改进建议。"""

    kind: RecommendationKind
    title: str
    rationale: str
    action: str

    def to_dict(self) -> dict[str, str]:
        """转换为报告写入器可以直接消费的字典。"""

        # 对外只暴露枚举值，保证 JSON 结果不依赖 Python 的枚举表现形式。
        return {
            "kind": self.kind.value,
            "title": self.title,
            "rationale": self.rationale,
            "action": self.action,
        }
