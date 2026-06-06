from agentops.core.memory import FailureMode, RepoMemory, ScoreTrend, SkillCandidate
from agentops.core.recommendation import Recommendation
from agentops.memory import (
    DeterministicMemoryNarrator,
    MemoryNarrator,
    build_repo_memory,
)
from agentops.parsers.history import HistoryRecord


def _finding(code: str, evidence: tuple[str, ...]) -> dict[str, object]:
    return {
        "code": code,
        "severity": "warning",
        "message": "m",
        "evidence": list(evidence),
    }


def _record(
    timestamp: str,
    score: int,
    *,
    findings: tuple[dict[str, object], ...] = (),
) -> HistoryRecord:
    return HistoryRecord(
        timestamp=timestamp,
        result={"score": score, "findings": list(findings), "intent_verdicts": []},
        verdict_summary={},
    )


class _RewriteSummaryNarrator:
    """只改写描述字段（summary）的叙述者替身；绝不改动结构事实。"""

    def __init__(self) -> None:
        self.called = False

    def narrate(self, memory: RepoMemory) -> RepoMemory:
        self.called = True
        rewritten = tuple(
            FailureMode(
                code=mode.code,
                occurrence_count=mode.occurrence_count,
                sample_count=mode.sample_count,
                hot_paths=mode.hot_paths,
                last_seen=mode.last_seen,
                summary=f"narrated: {mode.summary}",
            )
            for mode in memory.failure_modes
        )
        return RepoMemory(
            repo_root=memory.repo_root,
            sample_count=memory.sample_count,
            trend=memory.trend,
            failure_modes=rewritten,
            rule_candidates=memory.rule_candidates,
            skill_candidates=memory.skill_candidates,
        )


def test_build_repo_memory_composes_projection() -> None:
    records = (
        _record("t1", 85, findings=(_finding("undeclared_change", ("src/a.py",)),)),
        _record("t2", 80, findings=(_finding("undeclared_change", ("src/b.py",)),)),
    )

    memory = build_repo_memory(records, repo_root="/repo")

    assert isinstance(memory, RepoMemory)
    assert memory.repo_root == "/repo"
    assert memory.sample_count == 2
    assert isinstance(memory.trend, ScoreTrend)
    assert memory.trend.direction == "worsening"  # 85 -> 80
    assert [mode.code for mode in memory.failure_modes] == ["undeclared_change"]
    assert memory.failure_modes[0].occurrence_count == 2
    # 复现达阈值 → 规则候选与 skill 候选都非空，且为既有类型。
    assert memory.rule_candidates
    assert all(isinstance(rule, Recommendation) for rule in memory.rule_candidates)
    assert memory.skill_candidates
    assert all(isinstance(skill, SkillCandidate) for skill in memory.skill_candidates)


def test_build_repo_memory_is_deterministic() -> None:
    records = (
        _record(
            "t1",
            90,
            findings=(_finding("cross_module_breadth", ("src", "tests", "docs")),),
        ),
        _record(
            "t2",
            90,
            findings=(_finding("cross_module_breadth", ("src", "tests", "docs")),),
        ),
    )

    first = build_repo_memory(records, repo_root="/repo")
    second = build_repo_memory(records, repo_root="/repo")

    # 同样历史产出字节一致的记忆。
    assert first == second
    assert first.to_dict() == second.to_dict()


def test_default_narrator_returns_projection_unchanged() -> None:
    records = (_record("t1", 80, findings=(_finding("undeclared_change", ("x",)),)),)

    explicit = build_repo_memory(
        records, repo_root="/r", narrator=DeterministicMemoryNarrator()
    )
    default = build_repo_memory(records, repo_root="/r")

    # 默认就是确定性身份叙述者：显式传入与默认结果一致。
    assert explicit == default


def test_single_record_history_yields_unknown_direction() -> None:
    memory = build_repo_memory((_record("t1", 80),), repo_root="/r")

    assert memory.sample_count == 1
    assert memory.trend.direction == "unknown"


def test_injected_narrator_invoked_and_rewrites_only_descriptions() -> None:
    records = (
        _record("t1", 80, findings=(_finding("undeclared_change", ("src/a.py",)),)),
        _record("t2", 80, findings=(_finding("undeclared_change", ("src/b.py",)),)),
    )
    narrator = _RewriteSummaryNarrator()

    baseline = build_repo_memory(records, repo_root="/r")
    narrated = build_repo_memory(records, repo_root="/r", narrator=narrator)

    assert narrator.called, "injected narrator should be consulted"
    # 描述字段被改写。
    assert narrated.failure_modes[0].summary.startswith("narrated: ")
    # 结构事实（code / 计数 / 路径）保持不变——与意图判官“绝不重新推导文件集合”同构。
    assert [mode.code for mode in narrated.failure_modes] == [
        mode.code for mode in baseline.failure_modes
    ]
    assert (
        narrated.failure_modes[0].occurrence_count
        == baseline.failure_modes[0].occurrence_count
    )
    assert narrated.failure_modes[0].hot_paths == baseline.failure_modes[0].hot_paths


def test_memory_narrator_is_runtime_checkable_protocol() -> None:
    assert isinstance(_RewriteSummaryNarrator(), MemoryNarrator)
    assert isinstance(DeterministicMemoryNarrator(), MemoryNarrator)
