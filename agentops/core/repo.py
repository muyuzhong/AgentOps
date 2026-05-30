"""仓库画像数据模型。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepoProfile:
    """描述一次只读仓库扫描可以收集的基础信息。"""

    root: Path
    has_readme: bool = False
    constraint_files: tuple[str, ...] = ()
    test_directories: tuple[str, ...] = ()
    ci_files: tuple[str, ...] = ()
    project_markers: tuple[str, ...] = ()
    test_commands: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 友好结构。"""

        # 在模型边界显式转换 Path 和 tuple，避免序列化层猜测内部类型。
        return {
            "root": str(self.root),
            "has_readme": self.has_readme,
            "constraint_files": list(self.constraint_files),
            "test_directories": list(self.test_directories),
            "ci_files": list(self.ci_files),
            "project_markers": list(self.project_markers),
            "test_commands": list(self.test_commands),
        }
