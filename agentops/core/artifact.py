"""报告产物数据模型。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ArtifactKind(str, Enum):
    """第一阶段支持写出的产物类型。"""

    MARKDOWN_REPORT = "markdown_report"
    JSON_SCORE = "json_score"
    WORKFLOW_TRACE = "workflow_trace"
    EVAL_HISTORY = "eval_history"


@dataclass(frozen=True)
class Artifact:
    """记录一次评估流程生成的文件。"""

    kind: ArtifactKind
    path: Path

    def to_dict(self) -> dict[str, str]:
        """转换为 JSON 友好的产物描述。"""

        # 产物路径在写出边界统一转成字符串，便于后续报告聚合。
        return {
            "kind": self.kind.value,
            "path": str(self.path),
        }
