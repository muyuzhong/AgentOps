"""会话评测的意图裁决接口与确定性默认实现。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from agentops.core.eval import (
    SOURCE_DETERMINISTIC,
    VERDICT_NEEDS_REVIEW,
    IntentVerdict,
)
from agentops.core.session import TaskReport
from agentops.evaluators.scope_drift import ScopeDriftReport


@runtime_checkable
class IntentJudge(Protocol):
    """判断 scope findings 是否符合任务意图的可注入接口。"""

    def judge(
        self, task_report: TaskReport, report: ScopeDriftReport
    ) -> tuple[IntentVerdict, ...]:
        """返回对需要语义判断的 findings 的裁决。"""


class DeterministicIntentJudge:
    """默认判官：只标记 needs_review，不调用 LLM 或网络。"""

    def judge(
        self, task_report: TaskReport, report: ScopeDriftReport
    ) -> tuple[IntentVerdict, ...]:
        """为 llm_needed findings 生成确定性复核裁决。"""

        verdicts: list[IntentVerdict] = []
        for finding in report.findings:
            if not finding.llm_needed or finding.code != "intent_alignment":
                continue
            verdicts.append(
                IntentVerdict(
                    finding_code=finding.code,
                    evidence=finding.evidence,
                    verdict=VERDICT_NEEDS_REVIEW,
                    rationale=(
                        "Deterministic rules found a scope signal, but deciding "
                        "whether it fits the task intent requires semantic review."
                    ),
                    source=SOURCE_DETERMINISTIC,
                )
            )
        return tuple(verdicts)
