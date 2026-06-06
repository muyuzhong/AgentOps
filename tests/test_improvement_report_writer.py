import json
from pathlib import Path

from agentops.core.artifact import ArtifactKind
from agentops.core.asset import HookProposal, ImprovementAssets, InstructionSuggestion
from agentops.core.evaluation import Finding, Severity
from agentops.core.memory import SkillCandidate
from agentops.core.recommendation import Recommendation, RecommendationKind
from agentops.writers.improvement_report import ImprovementReportWriter

_BLOCK = (
    "<!-- agentops:repo-rules:start -->\n"
    "- Declare every changed file — List every touched path.\n"
    "<!-- agentops:repo-rules:end -->"
)


def _rule() -> Recommendation:
    return Recommendation(
        kind=RecommendationKind.DECLARE_CHANGED_FILES,
        title="Declare every changed file",
        rationale="recurred in 2/3 evals",
        action="List every touched path.",
    )


def _claude_suggestion() -> InstructionSuggestion:
    return InstructionSuggestion(
        target="CLAUDE.md",
        exists=True,
        line_count=250,
        additions=(_rule(),),
        subtractions=(
            Finding(
                code="instruction_over_budget",
                severity=Severity.WARNING,
                message="CLAUDE.md has 250 lines (budget 200); trim content.",
                evidence=("250 lines",),
            ),
        ),
        managed_block=_BLOCK,
    )


def _agents_suggestion() -> InstructionSuggestion:
    return InstructionSuggestion(
        target="AGENTS.md",
        exists=False,
        line_count=None,
        additions=(
            Recommendation(
                kind=RecommendationKind.ADD_CONSTRAINT_FILE,
                title="Create AGENTS.md with AgentOps repo rules",
                rationale="AGENTS.md is missing.",
                action="Create AGENTS.md and paste the block.",
            ),
            _rule(),
        ),
        subtractions=(),
        managed_block=_BLOCK,
    )


def _hook() -> HookProposal:
    return HookProposal(
        slug="check-session-log-stop-hook",
        failure_codes=("declared_not_changed", "undeclared_change"),
        event="Stop",
        title="Add a `check-session-log` Stop hook",
        rationale="recurred in 2/3 evals.",
        command="agentops check-session-log --repo .",
        settings_snippet='{\n  "hooks": {\n    "Stop": []\n  }\n}',
        evidence=("undeclared_change: 2/3 evals",),
    )


def _skill() -> SkillCandidate:
    return SkillCandidate(
        slug="declare-changed-files-checklist",
        title="Changed-files declaration checklist",
        trigger="Before ending a multi-file session.",
        rationale="r",
        evidence=("2/3 evals",),
    )


def _rich_assets() -> ImprovementAssets:
    return ImprovementAssets(
        repo_root="/repo",
        sample_count=3,
        trend_summary=(
            "Scope-discipline trend is worsening over 3 eval(s) (90->80); "
            "1 drift verdict(s)."
        ),
        instruction_suggestions=(_claude_suggestion(), _agents_suggestion()),
        hook_proposals=(_hook(),),
        skill_candidates=(_skill(),),
        workflow_steps=("Run `agentops eval --repo .` after each task.",),
    )


def _thin_assets() -> ImprovementAssets:
    return ImprovementAssets(
        repo_root="/repo",
        sample_count=1,
        trend_summary=(
            "Scope-discipline trend is unknown over 1 eval(s) (80->80); "
            "0 drift verdict(s)."
        ),
        instruction_suggestions=(
            InstructionSuggestion(
                target="CLAUDE.md",
                exists=True,
                line_count=10,
                additions=(),
                subtractions=(),
                managed_block="",
            ),
            InstructionSuggestion(
                target="AGENTS.md",
                exists=False,
                line_count=None,
                additions=(),
                subtractions=(),
                managed_block="",
            ),
        ),
        hook_proposals=(),
        skill_candidates=(),
        workflow_steps=("Run `agentops eval --repo .` after each task.",),
    )


def test_writes_four_artifacts(tmp_path: Path) -> None:
    artifacts = ImprovementReportWriter().write(_rich_assets(), tmp_path)

    assert {a.kind for a in artifacts} == {
        ArtifactKind.SUGGESTED_CLAUDE_MD,
        ArtifactKind.SUGGESTED_AGENTS_MD,
        ArtifactKind.HOOK_PROPOSALS,
        ArtifactKind.SUGGESTIONS_JSON,
    }
    assert (tmp_path / "suggested-claude-md.md").exists()
    assert (tmp_path / "suggested-agents-md.md").exists()
    assert (tmp_path / "suggested-hooks.md").exists()
    assert (tmp_path / "agentops-suggestions.json").exists()


def test_claude_md_has_fenced_block_and_trim(tmp_path: Path) -> None:
    ImprovementReportWriter().write(_rich_assets(), tmp_path)
    text = (tmp_path / "suggested-claude-md.md").read_text(encoding="utf-8")

    assert "```markdown" in text
    assert "agentops:repo-rules:start" in text
    assert "instruction_over_budget" in text  # 减法诊断
    assert "Declare every changed file" in text  # 加法 bullet


def test_agents_md_notes_missing_file(tmp_path: Path) -> None:
    ImprovementReportWriter().write(_rich_assets(), tmp_path)
    text = (tmp_path / "suggested-agents-md.md").read_text(encoding="utf-8")

    assert "missing" in text
    # 缺失文件没有减法诊断。
    assert "What to Trim" in text
    assert "- None." in text


def test_hooks_md_has_settings_snippet_steps_and_skills(tmp_path: Path) -> None:
    ImprovementReportWriter().write(_rich_assets(), tmp_path)
    text = (tmp_path / "suggested-hooks.md").read_text(encoding="utf-8")

    assert "```json" in text
    assert "check-session-log-stop-hook" in text
    assert "Workflow Guidance" in text
    assert "agentops eval" in text
    assert "Skill Scaffolds" in text
    assert "declare-changed-files-checklist" in text


def test_suggestions_json_mirrors_to_dict(tmp_path: Path) -> None:
    assets = _rich_assets()
    ImprovementReportWriter().write(assets, tmp_path)
    raw = (tmp_path / "agentops-suggestions.json").read_text(encoding="utf-8")

    assert raw.endswith("\n")
    assert json.loads(raw) == assets.to_dict()
    assert (
        raw
        == json.dumps(assets.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )


def test_artifacts_overwritten_not_appended(tmp_path: Path) -> None:
    writer = ImprovementReportWriter()
    writer.write(_rich_assets(), tmp_path)
    names = [
        "suggested-claude-md.md",
        "suggested-agents-md.md",
        "suggested-hooks.md",
        "agentops-suggestions.json",
    ]
    first = {name: (tmp_path / name).read_text(encoding="utf-8") for name in names}

    # 资产是可再生投影：二次运行覆盖写、字节一致。
    writer.write(_rich_assets(), tmp_path)

    for name in names:
        assert (tmp_path / name).read_text(encoding="utf-8") == first[name]


def test_thin_assets_render_cleanly(tmp_path: Path) -> None:
    artifacts = ImprovementReportWriter().write(_thin_assets(), tmp_path)
    claude = (tmp_path / "suggested-claude-md.md").read_text(encoding="utf-8")
    hooks = (tmp_path / "suggested-hooks.md").read_text(encoding="utf-8")

    assert len(artifacts) == 4
    # 无规则候选 → 明确说明，而非空块。
    assert "No recurring rules distilled yet." in claude
    # 空 hook / 空 skill 段渲染为 None。
    assert "- None." in hooks
