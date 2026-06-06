import json
from pathlib import Path

from agentops.core.artifact import ArtifactKind
from agentops.core.memory import FailureMode, RepoMemory, ScoreTrend, SkillCandidate
from agentops.core.recommendation import Recommendation, RecommendationKind
from agentops.writers.memory_report import MemoryReportWriter


def _full_memory() -> RepoMemory:
    return RepoMemory(
        repo_root="/repo",
        sample_count=3,
        trend=ScoreTrend(
            sample_count=3,
            first_score=70,
            last_score=90,
            average_score=80.0,
            direction="improving",
            drift_verdict_total=2,
        ),
        failure_modes=(
            FailureMode(
                code="undeclared_change",
                occurrence_count=2,
                sample_count=3,
                hot_paths=("src/billing.py", "src/auth.py"),
                last_seen="2026-06-06",
                summary="'undeclared_change' recurred in 2/3 evals; hot paths: ...",
            ),
        ),
        rule_candidates=(
            Recommendation(
                kind=RecommendationKind.DECLARE_CHANGED_FILES,
                title="Declare every changed file before ending the session",
                rationale="'undeclared_change' recurred in 2/3 evals; hot paths: ...",
                action="Add every touched path to the Changed Files section.",
            ),
        ),
        skill_candidates=(
            SkillCandidate(
                slug="declare-changed-files-checklist",
                title="Changed-files declaration checklist",
                trigger="Before ending any coding session that edits more than one file.",
                rationale="Undeclared changes recur across evals.",
                evidence=(
                    "recurred in 2/3 evals (last seen 2026-06-06)",
                    "hot paths: src/billing.py, src/auth.py",
                ),
            ),
        ),
    )


def _empty_memory() -> RepoMemory:
    return RepoMemory(
        repo_root="/repo",
        sample_count=1,
        trend=ScoreTrend(
            sample_count=1,
            first_score=80,
            last_score=80,
            average_score=80.0,
            direction="unknown",
            drift_verdict_total=0,
        ),
        failure_modes=(),
        rule_candidates=(),
        skill_candidates=(),
    )


def test_writes_three_artifacts(tmp_path: Path) -> None:
    artifacts = MemoryReportWriter().write(_full_memory(), tmp_path)

    assert {artifact.kind for artifact in artifacts} == {
        ArtifactKind.MEMORY_REPORT,
        ArtifactKind.MEMORY_JSON,
        ArtifactKind.SKILL_CANDIDATES,
    }
    assert (tmp_path / "agentops-memory.md").exists()
    assert (tmp_path / "agentops-memory.json").exists()
    assert (tmp_path / "skill-candidates.md").exists()


def test_memory_md_renders_trend_modes_rules_skills(tmp_path: Path) -> None:
    MemoryReportWriter().write(_full_memory(), tmp_path)
    text = (tmp_path / "agentops-memory.md").read_text(encoding="utf-8")

    # 趋势方向。
    assert "improving" in text
    # 失败模式：N/M + 热点路径 + 最近出现。
    assert "2/3" in text
    assert "src/billing.py" in text
    assert "2026-06-06" in text
    # 规则候选。
    assert "Declare every changed file before ending the session" in text
    # skill 候选。
    assert "Changed-files declaration checklist" in text


def test_memory_json_mirrors_to_dict_sorted_with_trailing_newline(
    tmp_path: Path,
) -> None:
    memory = _full_memory()
    MemoryReportWriter().write(memory, tmp_path)
    raw = (tmp_path / "agentops-memory.json").read_text(encoding="utf-8")

    assert raw.endswith("\n")
    assert json.loads(raw) == memory.to_dict()
    # 稳定结构：sort_keys + 两空格缩进 + 尾随换行。
    assert (
        raw
        == json.dumps(memory.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )


def test_skill_candidates_md_lists_each_candidate(tmp_path: Path) -> None:
    MemoryReportWriter().write(_full_memory(), tmp_path)
    text = (tmp_path / "skill-candidates.md").read_text(encoding="utf-8")

    assert "declare-changed-files-checklist" in text
    assert "Before ending any coding session" in text
    # 携带 N/M 历史证据。
    assert "2/3" in text


def test_artifacts_overwritten_not_appended_on_second_run(tmp_path: Path) -> None:
    writer = MemoryReportWriter()
    writer.write(_full_memory(), tmp_path)
    first_md = (tmp_path / "agentops-memory.md").read_text(encoding="utf-8")
    first_json = (tmp_path / "agentops-memory.json").read_text(encoding="utf-8")
    first_skills = (tmp_path / "skill-candidates.md").read_text(encoding="utf-8")

    # 记忆是历史的可再生投影：二次运行覆盖写、字节一致，绝不 append。
    writer.write(_full_memory(), tmp_path)

    assert (tmp_path / "agentops-memory.md").read_text(encoding="utf-8") == first_md
    assert (tmp_path / "agentops-memory.json").read_text(encoding="utf-8") == first_json
    assert (
        tmp_path / "skill-candidates.md"
    ).read_text(encoding="utf-8") == first_skills


def test_empty_but_valid_memory_renders_cleanly(tmp_path: Path) -> None:
    artifacts = MemoryReportWriter().write(_empty_memory(), tmp_path)

    md = (tmp_path / "agentops-memory.md").read_text(encoding="utf-8")
    skills = (tmp_path / "skill-candidates.md").read_text(encoding="utf-8")

    assert len(artifacts) == 3
    # 单样本：方向 unknown，空的失败模式/规则/skill 段渲染为 None。
    assert "unknown" in md
    assert "- None." in md
    assert "- None." in skills
