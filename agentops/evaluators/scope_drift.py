"""scope-drift 对账探针（Phase 3.5 SPIKE，验证完可丢弃）。

把一个 `TaskReport`（agent 的声明）与一个 `DiffSummary`（git 真相）做对账，
用纯确定性规则发现"文件集合 / 改动广度"层面的差值。本模块刻意只做一个维度
（scope drift），不评分、不调用 LLM；凡是需要判断"这个差值是否在任务意图之内"
的地方都显式标注 `llm_needed=True` 和 `# SPIKE: LLM insertion point`。

探针的真正产出是答案：确定性规则能走多远、Phase 4 必须在哪里引入 LLM。
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from agentops.core.evidence import DiffSummary
from agentops.core.session import TaskReport

# 改动横跨的顶层模块数达到该阈值时，标注 cross_module_breadth。
# （src + tests 这类常见组合不触发；阈值本身是否合理也是探针要回答的问题之一。）
MODULE_BREADTH_THRESHOLD = 3

# 根目录文件归入的伪模块名。
ROOT_MODULE = "(root)"

# 识别"看起来像文件名"的 token：含扩展名，如 auth.py、README.md。
_FILENAME_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]*\.[A-Za-z0-9_]+")


@dataclass(frozen=True)
class ScopeDriftFinding:
    """单条 scope-drift 发现。"""

    code: str
    evidence: tuple[str, ...]
    llm_needed: bool

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 友好结构。"""

        return {
            "code": self.code,
            "evidence": list(self.evidence),
            "llm_needed": self.llm_needed,
        }


@dataclass(frozen=True)
class ScopeDriftReport:
    """一次 scope-drift 对账的结果。"""

    declared_paths: tuple[str, ...]
    changed_paths: tuple[str, ...]
    findings: tuple[ScopeDriftFinding, ...]

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 友好结构。"""

        return {
            "declared_paths": list(self.declared_paths),
            "changed_paths": list(self.changed_paths),
            "findings": [finding.to_dict() for finding in self.findings],
        }


def reconcile_scope(
    task_report: TaskReport, diff_summary: DiffSummary
) -> ScopeDriftReport:
    """对账声明与真相，返回确定性的 scope-drift 发现。"""

    # 声明侧：context_used 始终来自自由文本抽取。
    declared_context = _extract_paths(task_report.context_used)
    # changed_files 是 agent 的显式声明：存在时优先把它作为"声明改动集合"，
    # 否则回退到从 changes 自由文本里抽取路径（兼容未升级协议的旧日志）。
    if task_report.changed_files:
        declared_changes = set(task_report.changed_files)
    else:
        declared_changes = _extract_paths(task_report.changes)
    declared_all = declared_context | declared_changes

    # 真相侧：diff 实际改动的路径（重命名取新路径）。
    changed_paths = tuple(sorted({changed.path for changed in diff_summary.files}))
    changed_set = set(changed_paths)

    findings: list[ScopeDriftFinding] = []

    # 规则一：真相里有、声明里完全没提到的改动 —— scope drift 信号。
    for path in changed_paths:
        if not _matches(path, declared_all):
            findings.append(
                ScopeDriftFinding(
                    code="undeclared_change",
                    evidence=(path,),
                    llm_needed=False,
                )
            )

    # 规则二：changes 里点名、但 diff 里没有的路径 —— 声明与真相不符。
    for path in sorted(declared_changes):
        if not _matches(path, changed_set):
            findings.append(
                ScopeDriftFinding(
                    code="declared_not_changed",
                    evidence=(path,),
                    llm_needed=False,
                )
            )

    # 规则三：改动横跨的顶层模块数量（广度是客观事实）。
    modules = sorted({_top_module(path) for path in changed_paths})
    if len(modules) >= MODULE_BREADTH_THRESHOLD:
        findings.append(
            ScopeDriftFinding(
                code="cross_module_breadth",
                evidence=tuple(modules),
                llm_needed=False,
            )
        )

    # 只要存在任一漂移信号，最终"是否在任务意图之内"的判断就超出了确定性规则的能力。
    if findings:
        # SPIKE: LLM insertion point —— 确定性规则只能发现"文件集合/广度"层面的差值，
        # 无法判断这些差值是否属于任务意图（顺带的合理改动 vs 真正越界、重构 vs 跑偏）。
        # Phase 4 在这里引入 LLM：输入声明 + 这些确定性发现，输出意图层面的裁决。
        findings.append(
            ScopeDriftFinding(
                code="intent_alignment",
                evidence=(
                    "deterministic rules detected scope signals; judging whether "
                    "they fall within the task's intent requires semantic reasoning",
                ),
                llm_needed=True,
            )
        )

    return ScopeDriftReport(
        declared_paths=tuple(sorted(declared_all)),
        changed_paths=changed_paths,
        findings=tuple(findings),
    )


def _extract_paths(texts: Iterable[str]) -> set[str]:
    """从自由文本中抽取路径型 token（含 `/` 或形如 name.ext）。"""

    found: set[str] = set()
    for text in texts:
        # 反引号当作分隔符，兼容 changes 文本里的 `inline code`。
        for raw_token in text.replace("`", " ").split():
            token = raw_token.strip().strip(",.;:!?()[]{}\"'").replace("\\", "/")
            if not token:
                continue
            if "/" in token or _FILENAME_RE.fullmatch(token):
                found.add(token)
    return found


def _matches(path: str, others: set[str]) -> bool:
    """路径是否与集合中的某项相等，或共享同一个 basename。

    basename 兜底能减少"裸文件名 vs 带目录路径"的误报；但它对不同目录下的同名文件
    会失效，这正是确定性匹配的天花板之一（详见探针 findings）。
    """

    if path in others:
        return True
    base = _basename(path)
    return any(_basename(other) == base for other in others)


def _basename(path: str) -> str:
    """返回路径最后一段。"""

    return path.rsplit("/", 1)[-1]


def _top_module(path: str) -> str:
    """返回路径的顶层目录；根目录文件归入伪模块名。"""

    return path.split("/", 1)[0] if "/" in path else ROOT_MODULE
