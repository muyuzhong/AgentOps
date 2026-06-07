from agentops.core.evaluation import Severity
from agentops.core.memory import RepoMemory, ScoreTrend
from agentops.core.recommendation import Recommendation, RecommendationKind
from agentops.improve.instructions import (
    INSTRUCTION_LINE_BUDGET,
    REPO_RULES_BLOCK_END,
    REPO_RULES_BLOCK_START,
    derive_instruction_suggestions,
)


def _rule(
    title: str = "Declare every changed file",
    action: str = "List every touched path.",
) -> Recommendation:
    return Recommendation(
        kind=RecommendationKind.DECLARE_CHANGED_FILES,
        title=title,
        rationale="'undeclared_change' recurred in 2/3 evals.",
        action=action,
    )


def _memory(*rule_candidates: Recommendation) -> RepoMemory:
    return RepoMemory(
        repo_root="/repo",
        sample_count=3,
        trend=ScoreTrend(
            sample_count=3,
            first_score=90,
            last_score=80,
            average_score=85.0,
            direction="worsening",
            drift_verdict_total=1,
        ),
        failure_modes=(),
        rule_candidates=tuple(rule_candidates),
        skill_candidates=(),
    )


def test_emits_claude_then_agents_in_fixed_order() -> None:
    suggestions = derive_instruction_suggestions(
        _memory(_rule()), {"CLAUDE.md": "x", "AGENTS.md": "y"}
    )

    assert [s.target for s in suggestions] == ["CLAUDE.md", "AGENTS.md"]


def test_emits_both_targets_even_when_absent_from_input() -> None:
    suggestions = derive_instruction_suggestions(_memory(_rule()), {})

    assert [s.target for s in suggestions] == ["CLAUDE.md", "AGENTS.md"]
    assert all(s.exists is False for s in suggestions)


def test_additions_reuse_rule_candidates_for_existing_file() -> None:
    rule = _rule()
    suggestions = derive_instruction_suggestions(
        _memory(rule), {"CLAUDE.md": "short\n", "AGENTS.md": "short\n"}
    )
    claude = suggestions[0]

    assert claude.exists is True
    assert claude.line_count == 1
    assert claude.additions == (rule,)


def test_missing_file_prepends_add_constraint_file_and_keeps_block() -> None:
    rule = _rule()
    suggestions = derive_instruction_suggestions(_memory(rule), {"CLAUDE.md": None})
    claude = suggestions[0]

    assert claude.exists is False
    assert claude.line_count is None
    # 文件缺失 → 在规则候选前补一条“建议新建”。
    assert claude.additions[0].kind == RecommendationKind.ADD_CONSTRAINT_FILE
    assert rule in claude.additions
    # 缺失文件仍渲染托管块（纯加法）。
    assert REPO_RULES_BLOCK_START in claude.managed_block
    # 缺失文件不产出减法诊断。
    assert claude.subtractions == ()


def test_managed_block_has_one_bullet_per_rule_candidate() -> None:
    rules = (_rule(title="A", action="do a"), _rule(title="B", action="do b"))
    suggestions = derive_instruction_suggestions(_memory(*rules), {"CLAUDE.md": "x"})
    block = suggestions[0].managed_block

    assert block.startswith(REPO_RULES_BLOCK_START)
    assert block.endswith(REPO_RULES_BLOCK_END)
    bullets = [line for line in block.splitlines() if line.startswith("- ")]
    assert bullets == [
        "- A: do a Evidence: 'undeclared_change' recurred in 2/3 evals.",
        "- B: do b Evidence: 'undeclared_change' recurred in 2/3 evals.",
    ]


def test_managed_block_empty_when_no_rule_candidates() -> None:
    suggestions = derive_instruction_suggestions(_memory(), {"CLAUDE.md": "x"})

    assert suggestions[0].managed_block == ""


def test_over_budget_file_yields_warning() -> None:
    big = "\n".join(f"line {i}" for i in range(INSTRUCTION_LINE_BUDGET + 5))
    suggestions = derive_instruction_suggestions(_memory(_rule()), {"CLAUDE.md": big})
    findings = {f.code: f for f in suggestions[0].subtractions}

    assert "instruction_over_budget" in findings
    assert findings["instruction_over_budget"].severity == Severity.WARNING
    assert any("lines" in item for item in findings["instruction_over_budget"].evidence)


def test_readme_duplication_yields_info() -> None:
    readme = "# Demo Project\n\nA tool that does things.\n\n## Install\n"
    # CLAUDE.md 内嵌 README 的首段（"# Demo Project"）。
    content = "# Demo Project\n\nProject rules:\n- be careful\n"
    suggestions = derive_instruction_suggestions(
        _memory(_rule()), {"CLAUDE.md": content}, readme=readme
    )
    findings = {f.code: f for f in suggestions[0].subtractions}

    assert "duplicates_readme" in findings
    assert findings["duplicates_readme"].severity == Severity.INFO


def test_short_non_duplicating_file_has_no_subtractions() -> None:
    readme = "# Totally Different\n\nUnrelated intro.\n"
    content = "Project rules:\n- declare files\n"
    suggestions = derive_instruction_suggestions(
        _memory(_rule()), {"CLAUDE.md": content}, readme=readme
    )

    # 短、不重复 → 不产出任何误报减法。
    assert suggestions[0].subtractions == ()


def test_empty_existing_file_has_zero_line_count_and_no_subtractions() -> None:
    suggestions = derive_instruction_suggestions(_memory(_rule()), {"CLAUDE.md": ""})
    claude = suggestions[0]

    assert claude.exists is True
    assert claude.line_count == 0
    assert claude.subtractions == ()
