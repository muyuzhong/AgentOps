"""分析工具层使用的确定性证据模型。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


def _require_non_negative_counts(message: str, *counts: int | None) -> None:
    """拒绝不能表示真实计数的负数。"""

    if any(
        count is not None and (type(count) is not int or count < 0)
        for count in counts
    ):
        raise ValueError(message)


class ChangeKind(str, Enum):
    """描述 git diff 中单个文件的变化类型。"""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass(frozen=True)
class ChangedFile:
    """保存一个文件的规范化 diff 证据。"""

    path: str
    change_kind: ChangeKind
    additions: int
    deletions: int
    previous_path: str | None = None

    def __post_init__(self) -> None:
        _require_non_negative_counts(
            "line counts must be non-negative",
            self.additions,
            self.deletions,
        )

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 友好结构。"""

        return {
            "path": self.path,
            "change_kind": self.change_kind.value,
            "additions": self.additions,
            "deletions": self.deletions,
            "previous_path": self.previous_path,
        }


@dataclass(frozen=True)
class DiffSummary:
    """聚合一次 unified diff 中的文件和行数变化。"""

    files: tuple[ChangedFile, ...]
    additions: int
    deletions: int

    def __post_init__(self) -> None:
        _require_non_negative_counts(
            "line counts must be non-negative",
            self.additions,
            self.deletions,
        )

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 友好结构。"""

        return {
            "files": [file.to_dict() for file in self.files],
            "additions": self.additions,
            "deletions": self.deletions,
        }


@dataclass(frozen=True)
class GitStatus:
    """保存只读 git 状态采集结果。"""

    repo_root: Path
    branch: str | None
    changed_paths: tuple[str, ...]
    untracked_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 友好结构。"""

        return {
            "repo_root": str(self.repo_root),
            "branch": self.branch,
            "changed_paths": list(self.changed_paths),
            "untracked_paths": list(self.untracked_paths),
        }


@dataclass(frozen=True)
class CIProfile:
    """保存 CI 配置文件和保守提取的验证命令。"""

    config_files: tuple[str, ...]
    validation_commands: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 友好结构。"""

        return {
            "config_files": list(self.config_files),
            "validation_commands": list(self.validation_commands),
        }


@dataclass(frozen=True)
class TestResult:
    """保存受支持测试框架的规范化摘要。"""

    framework: str
    passed: int | None = None
    failed: int | None = None
    skipped: int | None = None
    errors: int | None = None
    succeeded: bool | None = None

    def __post_init__(self) -> None:
        _require_non_negative_counts(
            "test counts must be non-negative",
            self.passed,
            self.failed,
            self.skipped,
            self.errors,
        )

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 友好结构。"""

        return {
            "framework": self.framework,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
            "succeeded": self.succeeded,
        }


@dataclass(frozen=True)
class ShellResult:
    """保存有界 shell 输出摘要及可选测试结果。"""

    command: str
    exit_code: int
    succeeded: bool
    summary: str
    truncated: bool = False
    test_result: TestResult | None = None

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 友好结构。"""

        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "succeeded": self.succeeded,
            "summary": self.summary,
            "truncated": self.truncated,
            "test_result": (
                self.test_result.to_dict() if self.test_result is not None else None
            ),
        }
