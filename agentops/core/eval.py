"""会话评测的结果模型与意图裁决模型。

EvalResult 是单次会话评测的完整结果：把 agent 声明的路径与 git 真相路径并列，
给出确定性的 scope-discipline 分数、带证据的诊断发现、可执行建议，以及对"差值
是否属于任务意图"的意图裁决（IntentVerdict）。

IntentVerdict 是 LLM 接缝的载体：确定性规则只能发现文件集合层的差值，是否越界
属于意图层判断。默认判官给出 needs_review（source=deterministic），真正的 LLM
判官后续按同一形状产出 source=llm 的裁决。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentops.core.evaluation import Finding
from agentops.core.recommendation import Recommendation

# 意图裁决取值：在意图内 / 漂移越界 / 需复核。
VERDICT_WITHIN_INTENT = "within_intent"
VERDICT_DRIFT = "drift"
VERDICT_NEEDS_REVIEW = "needs_review"
_ALLOWED_VERDICTS = (VERDICT_WITHIN_INTENT, VERDICT_DRIFT, VERDICT_NEEDS_REVIEW)

# 裁决来源：确定性默认判官 / LLM 判官。
SOURCE_DETERMINISTIC = "deterministic"
SOURCE_LLM = "llm"
_ALLOWED_SOURCES = (SOURCE_DETERMINISTIC, SOURCE_LLM)


@dataclass(frozen=True)
class IntentVerdict:
    """对一条需要语义判断的发现（如 intent_alignment）给出的意图裁决。"""

    finding_code: str
    evidence: tuple[str, ...]
    verdict: str
    rationale: str
    source: str

    def __post_init__(self) -> None:
        """校验取值，避免拼写错误悄悄进入产物。"""

        if self.verdict not in _ALLOWED_VERDICTS:
            raise ValueError(f"invalid intent verdict: {self.verdict!r}")
        if self.source not in _ALLOWED_SOURCES:
            raise ValueError(f"invalid intent verdict source: {self.source!r}")

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 友好结构。"""

        return {
            "finding_code": self.finding_code,
            "evidence": list(self.evidence),
            "verdict": self.verdict,
            "rationale": self.rationale,
            "source": self.source,
        }


@dataclass(frozen=True)
class EvalResult:
    """单次会话评测结果：声明 vs 真相、分数、诊断、建议与意图裁决。"""

    repo_root: Path
    task_title: str
    declared_paths: tuple[str, ...]
    changed_paths: tuple[str, ...]
    score: int
    findings: tuple[Finding, ...] = ()
    recommendations: tuple[Recommendation, ...] = ()
    intent_verdicts: tuple[IntentVerdict, ...] = ()

    def __post_init__(self) -> None:
        """与 readiness 一致，分数必须是 0..100 的严格整数（排除 bool）。"""

        if type(self.score) is not int or not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100")

    def to_dict(self) -> dict[str, object]:
        """递归转换为 writer 可直接写出的稳定结构（Path 转字符串、tuple 转 list）。"""

        return {
            "repo_root": str(self.repo_root),
            "task_title": self.task_title,
            "declared_paths": list(self.declared_paths),
            "changed_paths": list(self.changed_paths),
            "score": self.score,
            "findings": [finding.to_dict() for finding in self.findings],
            "recommendations": [
                recommendation.to_dict() for recommendation in self.recommendations
            ],
            "intent_verdicts": [verdict.to_dict() for verdict in self.intent_verdicts],
        }
