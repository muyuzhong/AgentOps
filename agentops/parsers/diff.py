"""将 unified git diff 规范化为公共证据模型。"""

from __future__ import annotations

import ast
import shlex
from dataclasses import dataclass

from agentops.core import ChangeKind, ChangedFile, DiffSummary


@dataclass
class _PendingFile:
    """暂存一个正在解析的文件变化。"""

    path: str
    change_kind: ChangeKind = ChangeKind.MODIFIED
    additions: int = 0
    deletions: int = 0
    previous_path: str | None = None

    def freeze(self) -> ChangedFile:
        """转换为不可变公共模型。"""

        return ChangedFile(
            path=self.path,
            change_kind=self.change_kind,
            additions=self.additions,
            deletions=self.deletions,
            previous_path=self.previous_path,
        )


def _strip_git_prefix(path: str) -> str:
    """移除 diff header 中的 a/ 或 b/ 前缀。"""

    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


def _decode_git_path(path: str) -> str:
    """解码 Git quoted path 中的 C 风格转义和 UTF-8 八进制字节。"""

    if not path.startswith('"') or not path.endswith('"'):
        return path
    try:
        decoded_path = ast.literal_eval(path)
    except (SyntaxError, ValueError):
        return path
    try:
        return decoded_path.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return decoded_path


def _parse_diff_path(line: str) -> str:
    """从 diff --git header 中读取目标路径。"""

    parts = shlex.split(line, posix=False)
    if len(parts) == 4:
        return _strip_git_prefix(_decode_git_path(parts[-1]))
    header = line.removeprefix("diff --git ")
    target_marker = " b/"
    marker_index = header.find(target_marker)
    while marker_index >= 0:
        previous_path = _strip_git_prefix(header[:marker_index])
        path = header[marker_index + len(target_marker) :]
        if previous_path == path:
            return path
        marker_index = header.find(target_marker, marker_index + 1)
    if target_marker not in header:
        return ""
    return header.rsplit(target_marker, maxsplit=1)[-1]


def _parse_patch_path(line: str) -> str:
    """从 --- 或 +++ header 中读取不带时间戳的文件路径。"""

    path = line[4:].split("\t", maxsplit=1)[0]
    return _strip_git_prefix(_decode_git_path(path))


class DiffParser:
    """解析 unified git diff 元数据和 hunk 行计数。"""

    def parse(self, content: str) -> DiffSummary:
        """按源顺序返回文件变化和聚合行数。"""

        files: list[ChangedFile] = []
        current: _PendingFile | None = None
        in_hunk = False

        for line in content.splitlines():
            if line.startswith("diff --git "):
                if current is not None:
                    files.append(current.freeze())
                current = _PendingFile(path=_parse_diff_path(line))
                in_hunk = False
                continue

            if current is None:
                continue
            if line.startswith("new file mode "):
                current.change_kind = ChangeKind.ADDED
                in_hunk = False
                continue
            if line.startswith("deleted file mode "):
                current.change_kind = ChangeKind.DELETED
                in_hunk = False
                continue
            if line.startswith("rename from "):
                current.change_kind = ChangeKind.RENAMED
                current.previous_path = _decode_git_path(
                    line.removeprefix("rename from ")
                )
                in_hunk = False
                continue
            if line.startswith("rename to "):
                current.change_kind = ChangeKind.RENAMED
                current.path = _decode_git_path(line.removeprefix("rename to "))
                in_hunk = False
                continue
            if not in_hunk and line.startswith(("--- ", "+++ ")):
                path = _parse_patch_path(line)
                if path != "/dev/null":
                    current.path = path
                continue
            if line.startswith("@@"):
                in_hunk = True
                continue
            if not in_hunk or line.startswith("\\"):
                continue
            if line.startswith("+"):
                current.additions += 1
            elif line.startswith("-"):
                current.deletions += 1

        if current is not None:
            files.append(current.freeze())

        return DiffSummary(
            files=tuple(files),
            additions=sum(file.additions for file in files),
            deletions=sum(file.deletions for file in files),
        )
