"""通过受控只读 git 子进程采集仓库证据。"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

from agentops.core import DiffSummary, GitStatus
from agentops.parsers import DiffParser


class GitAnalysisError(RuntimeError):
    """表示只读 git 证据采集失败。"""


def _decode_status_path(path: str) -> str:
    """解码 porcelain 中的 Git quoted path，并统一为 POSIX 路径。"""

    is_quoted = path.startswith('"') and path.endswith('"')
    if is_quoted:
        try:
            decoded_path = ast.literal_eval(path)
        except (SyntaxError, ValueError):
            decoded_path = path
        else:
            try:
                decoded_path = decoded_path.encode("latin-1").decode("utf-8")
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass
    else:
        decoded_path = path
    if is_quoted:
        return decoded_path
    return decoded_path.replace("\\", "/")


def _current_status_path(path: str) -> str:
    """提取 rename 行中引号外箭头之后的当前路径。"""

    in_quotes = False
    escaped = False
    for index, character in enumerate(path):
        if escaped:
            escaped = False
            continue
        if in_quotes and character == "\\":
            escaped = True
            continue
        if character == '"':
            in_quotes = not in_quotes
            continue
        if not in_quotes and path.startswith(" -> ", index):
            return path[index + len(" -> ") :]
    return path


def _parse_status_path(path: str) -> str:
    """提取普通或 rename porcelain 行中的当前路径。"""

    return _decode_status_path(_current_status_path(path))


class GitAnalyzer:
    """采集 branch、status 和 diff，不修改仓库状态。"""

    def _run_git(self, repo_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
        """执行一个允许的只读 git 命令，并封装进程失败。"""

        try:
            result = subprocess.run(
                ["git", *args],
                cwd=repo_path,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                shell=False,
            )
        except OSError as error:
            raise GitAnalysisError("git executable is unavailable") from error
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            if not message:
                message = f"git {' '.join(args)} failed with exit code {result.returncode}"
            raise GitAnalysisError(message)
        return result

    def _repo_root(self, repo_path: Path) -> Path:
        """校验目标目录，并返回 git 识别的仓库根目录。"""

        repo_path = Path(repo_path)
        if not repo_path.exists() or not repo_path.is_dir():
            raise GitAnalysisError("repository path must be an existing directory")
        result = self._run_git(repo_path, "rev-parse", "--show-toplevel")
        return Path(result.stdout.strip()).resolve()

    def status(self, repo_path: Path) -> GitStatus:
        """返回排序后的 tracked 与 untracked 工作区路径。"""

        repo_root = self._repo_root(repo_path)
        branch_result = self._run_git(repo_path, "branch", "--show-current")
        status_result = self._run_git(
            repo_path,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        )
        changed_paths: list[str] = []
        untracked_paths: list[str] = []
        for line in status_result.stdout.splitlines():
            if len(line) < 3:
                continue
            path = _parse_status_path(line[3:])
            if line[:2] == "??":
                untracked_paths.append(path)
            else:
                changed_paths.append(path)
        return GitStatus(
            repo_root=repo_root,
            branch=branch_result.stdout.strip() or None,
            changed_paths=tuple(sorted(changed_paths)),
            untracked_paths=tuple(sorted(untracked_paths)),
        )

    def diff(self, repo_path: Path) -> DiffSummary:
        """返回相对 HEAD 的规范化工作区 diff。"""

        self._repo_root(repo_path)
        result = self._run_git(
            repo_path,
            "diff",
            "--find-renames",
            "--no-ext-diff",
            "--unified=0",
            "HEAD",
        )
        return DiffParser().parse(result.stdout)
