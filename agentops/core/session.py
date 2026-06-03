"""有界 AgentOps 任务日志使用的会话证据模型。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VerificationRecord:
    """保存单条验证命令及其简短结果。"""

    command: str
    result: str

    def to_dict(self) -> dict[str, str]:
        """转换为稳定的 JSON 友好结构。"""

        return {
            "command": self.command,
            "result": self.result,
        }


@dataclass(frozen=True)
class TaskReport:
    """保存 coding agent 完成一个独立任务后的有界汇报。"""

    title: str
    goal: str
    context_used: tuple[str, ...] = ()
    changes: tuple[str, ...] = ()
    # agent 显式声明改动的文件路径；对账时优先于从自由文本抽取的路径。
    changed_files: tuple[str, ...] = ()
    verification: tuple[VerificationRecord, ...] = ()
    issues: tuple[str, ...] = ()
    evidence_references: tuple[str, ...] = ()
    truncated: bool = False

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 友好结构。"""

        return {
            "title": self.title,
            "goal": self.goal,
            "context_used": list(self.context_used),
            "changes": list(self.changes),
            "changed_files": list(self.changed_files),
            "verification": [record.to_dict() for record in self.verification],
            "issues": list(self.issues),
            "evidence_references": list(self.evidence_references),
            "truncated": self.truncated,
        }


@dataclass(frozen=True)
class SessionTrace:
    """聚合一份有界任务日志中的规范化任务汇报。"""

    source_path: Path
    tasks: tuple[TaskReport, ...]
    truncated: bool = False

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 友好结构。"""

        return {
            "source_path": str(self.source_path),
            "tasks": [task.to_dict() for task in self.tasks],
            "truncated": self.truncated,
        }
