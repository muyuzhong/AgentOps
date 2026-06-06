"""把规则候选投影为每个指令文件的加法托管块 + 确定性减法诊断（加法 + 减法）。

输入是文本内容（不是路径），保持投影是纯函数、可离线测试——与 build_repo_memory 接收
records 而非路径同构。加法复用 Phase 5 蒸馏出的规则候选（已是 Recommendation）；减法只做
两类确定性、可辩护的结构诊断——超出行预算、逐字重复 README——绝不做语法/风格层面的改写。
实际改写仍由用户决定，AgentOps 只产出可直接采纳的托管块文本与诊断（缺什么 / 多什么）。
"""

from __future__ import annotations

from agentops.core.asset import InstructionSuggestion
from agentops.core.evaluation import Finding, Severity
from agentops.core.memory import RepoMemory
from agentops.core.recommendation import Recommendation, RecommendationKind

# 指令文件行预算（provisional）：CLAUDE.md 每轮注入上下文，过长挤占有效 token；
# 与 scope 扣分权重、记忆复现阈值一样，待累积数据校准。
INSTRUCTION_LINE_BUDGET = 200

# repo-rules 托管块 marker：刻意区别于 init 的 agentops:session-protocol marker，
# 让采纳 Phase 6 规则块与 Phase 3 协议块可以在同一个 CLAUDE.md 中共存、互不干扰。
REPO_RULES_BLOCK_START = "<!-- agentops:repo-rules:start -->"
REPO_RULES_BLOCK_END = "<!-- agentops:repo-rules:end -->"

# 固定的目标指令文件与顺序：无论哪个存在都按此顺序产出建议。
_TARGETS = ("CLAUDE.md", "AGENTS.md")


def derive_instruction_suggestions(
    memory: RepoMemory,
    instructions: dict[str, str | None],
    readme: str | None = None,
) -> tuple[InstructionSuggestion, ...]:
    """把规则候选投影为每个指令文件的加法托管块 + 确定性减法诊断。

    ``instructions`` 形如 {"CLAUDE.md": content|None, "AGENTS.md": content|None}；
    content 为 None 表示文件缺失（纯加法 + 建议新建）。
    """

    managed_block = _render_managed_block(memory.rule_candidates)
    return tuple(
        _suggest_for_target(
            target, instructions.get(target), memory, readme, managed_block
        )
        for target in _TARGETS
    )


def _suggest_for_target(
    target: str,
    content: str | None,
    memory: RepoMemory,
    readme: str | None,
    managed_block: str,
) -> InstructionSuggestion:
    """为单个指令文件产出加法 + 减法建议。"""

    exists = content is not None
    line_count = len(content.splitlines()) if content is not None else None

    # 加法复用规则候选（已是 Recommendation，按记忆稳定顺序）；文件缺失时再补一条新建建议。
    additions: list[Recommendation] = list(memory.rule_candidates)
    if content is None:
        additions.insert(0, _create_file_recommendation(target))

    return InstructionSuggestion(
        target=target,
        exists=exists,
        line_count=line_count,
        additions=tuple(additions),
        subtractions=_subtractions(target, content, line_count, readme),
        managed_block=managed_block,
    )


def _create_file_recommendation(target: str) -> Recommendation:
    """文件缺失时建议新建（复用既有 ADD_CONSTRAINT_FILE，不另立 kind）。"""

    return Recommendation(
        kind=RecommendationKind.ADD_CONSTRAINT_FILE,
        title=f"Create {target} with AgentOps repo rules",
        rationale=(
            f"{target} is missing; recurring failure modes have nowhere to be "
            "encoded as project rules."
        ),
        action=(
            f"Create {target} and paste the agentops:repo-rules managed block below "
            "so the recurring rules ship with the repository."
        ),
    )


def _render_managed_block(rule_candidates: tuple[Recommendation, ...]) -> str:
    """渲染 agentops:repo-rules 托管块：每条规则候选一行 bullet；无规则时返回空串。

    确定性、稳定顺序、块内 LF 换行；writer 负责把它放进围栏代码块里供直接粘贴。
    """

    if not rule_candidates:
        return ""
    bullets = "\n".join(f"- {rule.title} — {rule.action}" for rule in rule_candidates)
    return f"{REPO_RULES_BLOCK_START}\n{bullets}\n{REPO_RULES_BLOCK_END}"


def _subtractions(
    target: str,
    content: str | None,
    line_count: int | None,
    readme: str | None,
) -> tuple[Finding, ...]:
    """确定性减法诊断：仅在文件存在时检查超长与 README 重复（保守，宁可沉默）。"""

    if content is None or line_count is None:
        return ()

    findings: list[Finding] = []

    if line_count > INSTRUCTION_LINE_BUDGET:
        findings.append(
            Finding(
                code="instruction_over_budget",
                severity=Severity.WARNING,
                message=(
                    f"{target} has {line_count} lines (budget {INSTRUCTION_LINE_BUDGET}); "
                    "trim tutorial or redundant content so injected context keeps room "
                    "for the task."
                ),
                evidence=(f"{line_count} lines",),
            )
        )

    duplicated = _readme_duplication(content, readme)
    if duplicated is not None:
        findings.append(
            Finding(
                code="duplicates_readme",
                severity=Severity.INFO,
                message=(
                    f"{target} repeats the README's opening paragraph; move the project "
                    "intro to the README and keep this file to project-specific rules."
                ),
                evidence=(duplicated,),
            )
        )

    return tuple(findings)


def _readme_duplication(content: str, readme: str | None) -> str | None:
    """若指令文件逐字包含 README 的首个非空段落，返回该段落首行；否则 None。

    保守起见：只在整段（连续非空行）逐字出现在指令文件中时才判定重复——误报比沉默更糟。
    """

    if not readme:
        return None
    paragraph = _first_paragraph(readme)
    if not paragraph:
        return None
    if paragraph in content:
        return paragraph.splitlines()[0]
    return None


def _first_paragraph(text: str) -> str:
    """取文本中第一段连续非空行（跳过开头空行）；无内容时返回空串。"""

    lines = text.splitlines()
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    collected: list[str] = []
    for line in lines[start:]:
        if not line.strip():
            break
        collected.append(line)
    return "\n".join(collected)
