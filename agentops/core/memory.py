"""仓库记忆的核心数据模型。

RepoMemory 是 `eval-history.jsonl` 的确定性投影：把累积的历史评测蒸馏成四样东西
——分数/漂移走向（ScoreTrend）、反复出现的失败模式（FailureMode）、带证据的规则
候选（复用现有 Recommendation）、可复用的 skill 候选（SkillCandidate）。每一项都
带"在 N/M 次评测中复现"的历史证据。

这些模型只是历史的投影载体：同样的历史产出字节一致的记忆。模型本身不计算、不读盘、
不触网，计数/聚类/排序由 `agentops/memory/` 下的确定性函数负责，叙述富化由后续的
MemoryNarrator 接缝负责——它只能改写描述字段，绝不改动这里记录的结构事实。
"""

from __future__ import annotations

from dataclasses import dataclass

from agentops.core.recommendation import Recommendation


@dataclass(frozen=True)
class ScoreTrend:
    """跨评测的 scope-discipline 分数与漂移走向（确定性投影）。"""

    sample_count: int  # 参与统计的评测条数
    first_score: int | None  # 最早一次分数（无样本时 None）
    last_score: int | None  # 最近一次分数（无样本时 None）
    average_score: float | None  # 平均分（固定小数位，保证可复现）
    direction: str  # "improving" | "worsening" | "flat" | "unknown"（<2 样本为 unknown）
    drift_verdict_total: int  # 累积 drift 裁决数（取自历史行的 verdict_summary）

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 友好结构（None 原样保留）。"""

        return {
            "sample_count": self.sample_count,
            "first_score": self.first_score,
            "last_score": self.last_score,
            "average_score": self.average_score,
            "direction": self.direction,
            "drift_verdict_total": self.drift_verdict_total,
        }


@dataclass(frozen=True)
class FailureMode:
    """一种跨评测反复出现的失败模式（按稳定 code 聚类）。"""

    code: str  # undeclared_change / declared_not_changed / cross_module_breadth / confirmed_drift
    occurrence_count: int  # 出现该模式的评测次数（N/M 的 N）
    sample_count: int  # 统计窗口内的评测总数（N/M 的 M）
    hot_paths: tuple[str, ...]  # 反复出现的证据路径/模块（频次降序、路径升序，结果有界）
    last_seen: str  # 最近一次出现的 timestamp
    summary: str  # 确定性模板摘要（叙述接缝可后续富化）

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 友好结构（tuple 转 list）。"""

        return {
            "code": self.code,
            "occurrence_count": self.occurrence_count,
            "sample_count": self.sample_count,
            "hot_paths": list(self.hot_paths),
            "last_seen": self.last_seen,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class SkillCandidate:
    """从反复失败模式提炼的可复用 skill 候选（候选数据，非最终 skill）。"""

    slug: str  # 稳定 id，如 declare-changed-files-checklist
    title: str
    trigger: str  # 何时该加载这个 skill
    rationale: str  # 为什么（确定性模板，叙述接缝可后续富化）
    evidence: tuple[str, ...]  # 历史证据：N/M + 相关路径

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 友好结构（tuple 转 list）。"""

        return {
            "slug": self.slug,
            "title": self.title,
            "trigger": self.trigger,
            "rationale": self.rationale,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class RepoMemory:
    """eval-history.jsonl 的确定性投影：趋势 + 失败模式 + 规则候选 + skill 候选。"""

    repo_root: str
    sample_count: int
    trend: ScoreTrend
    failure_modes: tuple[FailureMode, ...]
    rule_candidates: tuple[Recommendation, ...]  # 复用现有 Recommendation，不新增模型
    skill_candidates: tuple[SkillCandidate, ...]

    def to_dict(self) -> dict[str, object]:
        """递归转换为 writer 可直接写出的稳定结构（每层模型自行序列化）。"""

        return {
            "repo_root": self.repo_root,
            "sample_count": self.sample_count,
            "trend": self.trend.to_dict(),
            "failure_modes": [mode.to_dict() for mode in self.failure_modes],
            "rule_candidates": [
                recommendation.to_dict() for recommendation in self.rule_candidates
            ],
            "skill_candidates": [
                candidate.to_dict() for candidate in self.skill_candidates
            ],
        }
