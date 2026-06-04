from __future__ import annotations

import json

from agentops.core.eval import (
    SOURCE_DETERMINISTIC,
    SOURCE_LLM,
    VERDICT_DRIFT,
    VERDICT_NEEDS_REVIEW,
    VERDICT_WITHIN_INTENT,
    IntentVerdict,
)
from agentops.core.evidence import ChangedFile, ChangeKind, DiffSummary
from agentops.core.session import TaskReport
from agentops.evaluators.scope_drift import reconcile_scope
from agentops.judges.intent import DeterministicIntentJudge, IntentJudge
from agentops.judges.llm_intent import LLMIntentJudge
from agentops.llm.client import LLMError, LLMRequest, LLMResponse


class _StubClient:
    """记录请求并回放预置文本（或抛错）的 LLMClient 替身；绝不触网。"""

    def __init__(
        self, *, text: str | None = None, error: Exception | None = None
    ) -> None:
        self._text = text
        self._error = error
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        assert self._text is not None
        return LLMResponse(text=self._text)


class _RecordingFallback:
    """记录是否被调用的降级判官替身。"""

    def __init__(self) -> None:
        self.calls = 0

    def judge(self, task_report: TaskReport, report: object) -> tuple[IntentVerdict, ...]:
        self.calls += 1
        return (
            IntentVerdict(
                finding_code="intent_alignment",
                evidence=("signal",),
                verdict=VERDICT_NEEDS_REVIEW,
                rationale="fallback used",
                source=SOURCE_DETERMINISTIC,
            ),
        )


def _diff(*paths: str) -> DiffSummary:
    files = tuple(
        ChangedFile(path=path, change_kind=ChangeKind.MODIFIED, additions=1, deletions=0)
        for path in paths
    )
    return DiffSummary(files=files, additions=len(files), deletions=0)


def _undeclared_scope():
    """声明 src/auth.py，真相多出未声明的 src/billing.py。"""

    report = TaskReport(
        title="Fix login",
        goal="Repair the broken login flow",
        changes=("Implemented the login fix",),
        changed_files=("src/auth.py",),
    )
    scope = reconcile_scope(report, _diff("src/auth.py", "src/billing.py"))
    return report, scope


def _verdict_json(verdict: str, evidence: list[str], code: str = "undeclared_change") -> str:
    return json.dumps(
        [
            {
                "finding_code": code,
                "evidence": evidence,
                "verdict": verdict,
                "rationale": "because reasons",
            }
        ]
    )


def test_within_intent_response_yields_llm_verdict() -> None:
    report, scope = _undeclared_scope()
    client = _StubClient(text=_verdict_json(VERDICT_WITHIN_INTENT, ["src/billing.py"]))

    verdicts = LLMIntentJudge(client).judge(report, scope)

    assert len(verdicts) == 1
    assert verdicts[0].finding_code == "undeclared_change"
    assert verdicts[0].evidence == ("src/billing.py",)
    assert verdicts[0].verdict == VERDICT_WITHIN_INTENT
    assert verdicts[0].source == SOURCE_LLM
    assert verdicts[0].rationale == "because reasons"


def test_drift_response_yields_llm_verdict() -> None:
    report, scope = _undeclared_scope()
    client = _StubClient(text=_verdict_json(VERDICT_DRIFT, ["src/billing.py"]))

    verdicts = LLMIntentJudge(client).judge(report, scope)

    assert verdicts[0].verdict == VERDICT_DRIFT
    assert verdicts[0].source == SOURCE_LLM


def test_clean_report_yields_no_verdicts_and_no_call() -> None:
    report = TaskReport(title="t", goal="g", changed_files=("src/auth.py",))
    scope = reconcile_scope(report, _diff("src/auth.py"))
    client = _StubClient(text="[]")

    verdicts = LLMIntentJudge(client).judge(report, scope)

    assert verdicts == ()
    # 干净报告不应触达模型。
    assert client.requests == []


def test_fenced_json_response_is_parsed() -> None:
    # mimo 等推理模型会把 JSON 包在 ```json ... ``` 代码块里，judge 必须能解出来。
    report, scope = _undeclared_scope()
    fenced = "```json\n" + _verdict_json(VERDICT_DRIFT, ["src/billing.py"]) + "\n```"
    client = _StubClient(text=fenced)

    verdicts = LLMIntentJudge(client).judge(report, scope)

    assert verdicts[0].verdict == VERDICT_DRIFT
    assert verdicts[0].source == SOURCE_LLM


def test_multiple_findings_yield_per_finding_verdicts() -> None:
    # 不声明任何文件，真相横跨 3 个模块：3 条 undeclared + 1 条 cross_module_breadth。
    report = TaskReport(title="Broad", goal="Touch one module", changes=())
    scope = reconcile_scope(report, _diff("src/a.py", "tests/b.py", "docs/c.md"))
    payload = [
        {
            "finding_code": "undeclared_change",
            "evidence": ["src/a.py"],
            "verdict": VERDICT_WITHIN_INTENT,
            "rationale": "core change",
        },
        {
            "finding_code": "undeclared_change",
            "evidence": ["tests/b.py"],
            "verdict": VERDICT_WITHIN_INTENT,
            "rationale": "tests for the change",
        },
        {
            "finding_code": "undeclared_change",
            "evidence": ["docs/c.md"],
            "verdict": VERDICT_DRIFT,
            "rationale": "doc edit unrelated",
        },
        {
            "finding_code": "cross_module_breadth",
            "evidence": ["docs", "src", "tests"],
            "verdict": VERDICT_DRIFT,
            "rationale": "spread too wide",
        },
    ]
    client = _StubClient(text=json.dumps(payload))

    verdicts = LLMIntentJudge(client).judge(report, scope)

    codes = sorted({v.finding_code for v in verdicts})
    assert codes == ["cross_module_breadth", "undeclared_change"]
    assert len(verdicts) == 4
    assert all(v.source == SOURCE_LLM for v in verdicts)
    drift = [v for v in verdicts if v.verdict == VERDICT_DRIFT]
    assert len(drift) == 2


def test_llm_error_degrades_to_deterministic() -> None:
    report, scope = _undeclared_scope()
    client = _StubClient(error=LLMError("network down"))

    verdicts = LLMIntentJudge(client).judge(report, scope)

    expected = DeterministicIntentJudge().judge(report, scope)
    assert verdicts == expected
    assert verdicts[0].verdict == VERDICT_NEEDS_REVIEW
    assert verdicts[0].source == SOURCE_DETERMINISTIC


def test_unparsable_response_degrades_to_deterministic() -> None:
    report, scope = _undeclared_scope()
    client = _StubClient(text="I cannot answer in JSON, sorry.")

    verdicts = LLMIntentJudge(client).judge(report, scope)

    assert verdicts == DeterministicIntentJudge().judge(report, scope)
    assert verdicts[0].source == SOURCE_DETERMINISTIC


def test_invalid_verdict_value_degrades_to_deterministic() -> None:
    report, scope = _undeclared_scope()
    # needs_review 不是 LLM 路径的合法取值；应触发降级。
    client = _StubClient(text=_verdict_json("needs_review", ["src/billing.py"]))

    verdicts = LLMIntentJudge(client).judge(report, scope)

    assert verdicts[0].source == SOURCE_DETERMINISTIC


def test_incomplete_coverage_degrades_to_deterministic() -> None:
    # 真相有两个未声明改动，模型只裁决其中一个 → 覆盖不全 → 降级。
    report = TaskReport(title="t", goal="g", changed_files=("src/auth.py",))
    scope = reconcile_scope(report, _diff("src/auth.py", "src/billing.py", "src/extra.py"))
    client = _StubClient(text=_verdict_json(VERDICT_DRIFT, ["src/billing.py"]))

    verdicts = LLMIntentJudge(client).judge(report, scope)

    assert verdicts[0].source == SOURCE_DETERMINISTIC


def test_prompt_carries_goal_and_findings_without_re_deriving() -> None:
    report, scope = _undeclared_scope()
    client = _StubClient(text=_verdict_json(VERDICT_WITHIN_INTENT, ["src/billing.py"]))

    LLMIntentJudge(client).judge(report, scope)

    assert len(client.requests) == 1
    request = client.requests[0]
    # 用户消息携带意图与待裁决的具体路径。
    assert "Repair the broken login flow" in request.user
    assert "src/billing.py" in request.user
    # 系统消息明确禁止模型自己重新推导文件集合。
    lowered = request.system.lower()
    assert "already determined" in lowered
    assert "do not" in lowered


def test_custom_fallback_is_used_on_degrade() -> None:
    report, scope = _undeclared_scope()
    fallback = _RecordingFallback()
    client = _StubClient(error=LLMError("boom"))

    verdicts = LLMIntentJudge(client, fallback=fallback).judge(report, scope)

    assert fallback.calls == 1
    assert verdicts[0].rationale == "fallback used"


def test_judge_requests_generous_max_tokens_for_reasoning_models() -> None:
    # 推理模型把"思考"算进 max_tokens；上限太小会截断 JSON 而被迫降级。
    # 锁定一个充裕的上限，避免日后回退到会触发截断的小值。
    report, scope = _undeclared_scope()
    client = _StubClient(text=_verdict_json(VERDICT_WITHIN_INTENT, ["src/billing.py"]))

    LLMIntentJudge(client).judge(report, scope)

    assert client.requests[0].max_tokens >= 2048


def test_declared_not_changed_only_degrades_without_calling_model() -> None:
    # 只有 declared_not_changed 触发 intent_alignment：没有可逐条裁决的 gap。
    report = TaskReport(
        title="t", goal="g", changed_files=("src/auth.py", "src/missing.py")
    )
    scope = reconcile_scope(report, _diff("src/auth.py"))
    fallback = _RecordingFallback()
    client = _StubClient(text="[]")

    verdicts = LLMIntentJudge(client, fallback=fallback).judge(report, scope)

    assert client.requests == []
    assert fallback.calls == 1
    assert verdicts[0].source == SOURCE_DETERMINISTIC


def test_llm_intent_judge_satisfies_protocol() -> None:
    assert isinstance(LLMIntentJudge(_StubClient(text="[]")), IntentJudge)
