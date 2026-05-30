"""仓库 AI coding readiness 评估数据模型。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agentops.core.recommendation import Recommendation
from agentops.core.repo import RepoProfile


class Severity(str, Enum):
    """诊断发现的严重程度。"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Finding:
    """保存一条带证据的 readiness 诊断发现。"""

    code: str
    severity: Severity
    message: str
    evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """转换为 JSON 友好的诊断结构。"""

        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class ReadinessReport:
    """聚合仓库画像、分数、诊断发现和改进建议。"""

    profile: RepoProfile
    score: int
    findings: tuple[Finding, ...] = ()
    recommendations: tuple[Recommendation, ...] = ()

    def __post_init__(self) -> None:
        """限制 readiness 分数落在可解释的百分制范围内。"""

        # 百分制边界在模型入口校验，避免下游报告出现无效分数。
        if not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100")

    def to_dict(self) -> dict[str, object]:
        """递归转换为 Artifact Writer 可以直接写出的结构。"""

        # 每层模型自行负责序列化，保持 JSON 输出契约清晰且稳定。
        return {
            "profile": self.profile.to_dict(),
            "score": self.score,
            "findings": [finding.to_dict() for finding in self.findings],
            "recommendations": [
                recommendation.to_dict() for recommendation in self.recommendations
            ],
        }
