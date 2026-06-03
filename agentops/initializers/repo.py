"""安装 AgentOps 任务日志协议的显式仓库初始化器。"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile


INSTRUCTION_BLOCK_START = "<!-- agentops:session-protocol:start -->"
INSTRUCTION_BLOCK_END = "<!-- agentops:session-protocol:end -->"
IGNORE_BLOCK_START = "# agentops:session-log:start"
IGNORE_BLOCK_END = "# agentops:session-log:end"

INSTRUCTION_BLOCK = (
    f"{INSTRUCTION_BLOCK_START}\n"
    "完成每个独立开发任务后，请按 `.agentops/session-protocol.md` 的格式，\n"
    "向 `.agentops/agentops-session.md` 追加简短汇报。\n"
    f"{INSTRUCTION_BLOCK_END}\n"
)

IGNORE_BLOCK = (
    f"{IGNORE_BLOCK_START}\n"
    "agentops-session.md\n"
    f"{IGNORE_BLOCK_END}\n"
)

SESSION_PROTOCOL = """# AgentOps 任务日志协议

完成每个独立开发任务后，请向 `.agentops/agentops-session.md` 追加一份简短汇报。
保持内容有界，只引用必要的 transcript 事件、行号或外部归档指针，不要复制完整聊天记录。

```markdown
## Task: <任务标题>

### Goal
<目标>

### Context Used
- `<读取的文件或上下文>`

### Changes
- <完成的修改>

### Changed Files
- `<改动的文件路径>`

### Verification
- Command: `<执行的命令>`
- Result: `<简短结果>`

### Issues
- <遇到的问题或无>

### Evidence References
- Transcript: `<事件 ID、行号或归档指针>`
- Diff: `<相关路径>`
```
"""


class SessionLogPolicy(str, Enum):
    """描述初始化器如何处理本地任务日志的 Git 策略。"""

    PRIVATE = "private"
    TRACKED = "tracked"
    UNMANAGED = "unmanaged"


@dataclass(frozen=True)
class InitResult:
    """记录显式初始化修改过的路径。"""

    repo_path: Path
    session_log_policy: SessionLogPolicy
    changed_paths: tuple[Path, ...]


def _split_line_ending(line: str) -> tuple[str, str]:
    """拆分单行内容和原始换行符。"""

    for line_ending in ("\r\n", "\n", "\r"):
        if line.endswith(line_ending):
            return line[: -len(line_ending)], line_ending
    return line, ""


def _leading_line_ending(content: str) -> str:
    """返回文本开头紧邻的一个换行符。"""

    for line_ending in ("\r\n", "\n", "\r"):
        if content.startswith(line_ending):
            return line_ending
    return ""


def _preferred_line_ending(content: str) -> str:
    """沿用现有文本的换行风格，新文件默认使用 LF。"""

    if "\r\n" in content:
        return "\r\n"
    if "\n" in content:
        return "\n"
    if "\r" in content:
        return "\r"
    return "\n"


def _normalize_line_endings(content: str, line_ending: str) -> str:
    """只对 AgentOps 自己生成的规范文本应用目标换行风格。"""

    return content.replace("\r\n", "\n").replace("\r", "\n").replace(
        "\n",
        line_ending,
    )


def _find_managed_blocks(content: str, start: str, end: str) -> tuple[tuple[int, int], ...]:
    """定位独立 marker 行围成的托管块，并拒绝孤立或嵌套 marker。"""

    blocks: list[tuple[int, int]] = []
    current_start: int | None = None
    offset = 0
    for line in content.splitlines(keepends=True):
        line_content, _ = _split_line_ending(line)
        if line_content == start:
            if current_start is not None:
                raise ValueError("managed block markers are malformed")
            current_start = offset
        elif line_content == end:
            if current_start is None:
                raise ValueError("managed block markers are malformed")
            blocks.append((current_start, offset + len(line_content)))
            current_start = None
        offset += len(line)
    if current_start is not None:
        raise ValueError("managed block markers are malformed")
    return tuple(blocks)


def _append_block(content: str, block: str, line_ending: str) -> str:
    """在用户内容后追加规范块，同时保留整洁换行。"""

    if not content:
        return block
    if content.endswith(("\n", "\r")):
        return f"{content}{block}"
    return f"{content}{line_ending}{block}"


def _render_managed_block(
    content: str,
    *,
    start: str,
    end: str,
    block: str | None,
) -> str:
    """刷新、折叠或移除托管块，不改写块外用户内容。"""

    blocks = _find_managed_blocks(content, start, end)
    line_ending = _preferred_line_ending(content)
    normalized_block = (
        _normalize_line_endings(block, line_ending) if block is not None else None
    )
    if not blocks:
        return (
            content
            if normalized_block is None
            else _append_block(content, normalized_block, line_ending)
        )

    rendered: list[str] = []
    cursor = 0
    for index, (block_start, block_end) in enumerate(blocks):
        rendered.append(content[cursor:block_start])
        if index == 0 and normalized_block is not None:
            rendered.append(normalized_block.rstrip("\r\n"))
        cursor = block_end
        removing_block = normalized_block is None or index > 0
        if removing_block:
            following_line_ending = _leading_line_ending(content[cursor:])
            if following_line_ending:
                cursor += len(following_line_ending)
    rendered.append(content[cursor:])

    result = "".join(rendered)
    if result and not result.endswith(("\n", "\r")):
        result += line_ending
    return result


def _read_existing_file(path: Path, *, error_message: str) -> str | None:
    """读取可选普通文件，并让目录型路径在写入前失败。"""

    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(error_message)
    with path.open("r", encoding="utf-8", newline="") as existing_file:
        return existing_file.read()


def _missing_parent_directories(path: Path) -> tuple[Path, ...]:
    """返回写入目标前尚不存在的父目录，供失败时清理。"""

    missing: list[Path] = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    return tuple(missing)


def _validate_writable_destination(path: Path) -> None:
    """在 staging 前拒绝明显不可替换的目标。"""

    if path.exists():
        mode = path.stat().st_mode
        if not os.access(path, os.W_OK) or not mode & stat.S_IWRITE:
            raise PermissionError(f"destination is not writable: {path}")

    existing_parent = path.parent
    while not existing_parent.exists():
        existing_parent = existing_parent.parent
    if not existing_parent.is_dir() or not os.access(existing_parent, os.W_OK):
        raise PermissionError(f"destination directory is not writable: {path.parent}")


def _stage_write(path: Path, content: str) -> Path:
    """在目标同目录准备完整临时文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
        return temporary_path
    except Exception:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
        raise


def _replace_staged(staged_path: Path, destination: Path) -> None:
    """使用同目录 staged 文件原子替换目标。"""

    staged_path.replace(destination)


def _restore_path(path: Path, original_content: str | None) -> None:
    """尽力恢复已经替换过的文件。"""

    if original_content is None:
        path.unlink(missing_ok=True)
        return
    staged_path = _stage_write(path, original_content)
    try:
        _replace_staged(staged_path, path)
    finally:
        if staged_path.exists():
            staged_path.unlink()


def _apply_planned_contents(planned_contents: dict[Path, str]) -> tuple[Path, ...]:
    """统一 staging 后写入；任一 replace 失败时回滚此前文件。"""

    original_contents = {
        path: _read_existing_file(
            path,
            error_message="managed path must be a regular file",
        )
        for path in planned_contents
    }
    changed_contents = {
        path: content
        for path, content in planned_contents.items()
        if original_contents[path] != content
    }
    if not changed_contents:
        return ()

    for path in changed_contents:
        _validate_writable_destination(path)

    created_directories = {
        directory
        for path in changed_contents
        for directory in _missing_parent_directories(path)
    }
    staged_paths: dict[Path, Path] = {}
    replaced_paths: list[Path] = []
    try:
        for path, content in changed_contents.items():
            staged_paths[path] = _stage_write(path, content)
        for path, staged_path in staged_paths.items():
            _replace_staged(staged_path, path)
            replaced_paths.append(path)
    except Exception:
        for path in reversed(replaced_paths):
            _restore_path(path, original_contents[path])
        raise
    finally:
        for staged_path in staged_paths.values():
            if staged_path.exists():
                staged_path.unlink()
        for directory in sorted(
            created_directories,
            key=lambda candidate: len(candidate.parts),
            reverse=True,
        ):
            if directory.exists() and not any(directory.iterdir()):
                directory.rmdir()

    return tuple(sorted(changed_contents, key=lambda path: path.as_posix()))


def _instruction_paths(repo_path: Path) -> tuple[Path, ...]:
    """选择已有 agent 指令文件，或回退到 rule.md。"""

    candidates = tuple(repo_path / name for name in ("CLAUDE.md", "AGENTS.md"))
    existing = tuple(path for path in candidates if path.exists())
    return existing or (repo_path / "rule.md",)


def run_init(repo_path: Path, session_log_policy: SessionLogPolicy) -> InitResult:
    """显式安装任务日志协议，并返回实际变化路径。"""

    repo_path = Path(repo_path)
    if not repo_path.exists() or not repo_path.is_dir():
        raise ValueError("repository path must be an existing directory")

    session_log_policy = SessionLogPolicy(session_log_policy)
    agentops_path = repo_path / ".agentops"
    if agentops_path.exists() and not agentops_path.is_dir():
        raise ValueError(".agentops path must be a directory")

    instruction_paths = _instruction_paths(repo_path)
    instruction_contents = {
        path: _read_existing_file(
            path,
            error_message="instruction path must be a regular file",
        )
        for path in instruction_paths
    }

    protocol_path = agentops_path / "session-protocol.md"
    session_log_path = agentops_path / "agentops-session.md"
    ignore_path = agentops_path / ".gitignore"
    protocol_content = _read_existing_file(
        protocol_path,
        error_message="managed path must be a regular file",
    )
    session_log_content = _read_existing_file(
        session_log_path,
        error_message="managed path must be a regular file",
    )
    ignore_content = _read_existing_file(
        ignore_path,
        error_message="managed path must be a regular file",
    )

    # 在任何写入前校验并渲染全部托管文本，避免 marker 异常造成部分更新。
    rendered_instructions = {
        path: _render_managed_block(
            content or "",
            start=INSTRUCTION_BLOCK_START,
            end=INSTRUCTION_BLOCK_END,
            block=INSTRUCTION_BLOCK,
        )
        for path, content in instruction_contents.items()
    }
    rendered_ignore = ignore_content
    if ignore_content is not None:
        # unmanaged 仍校验现有 marker，但不接管用户内容。
        _find_managed_blocks(ignore_content, IGNORE_BLOCK_START, IGNORE_BLOCK_END)
    if session_log_policy is SessionLogPolicy.PRIVATE:
        rendered_ignore = _render_managed_block(
            ignore_content or "",
            start=IGNORE_BLOCK_START,
            end=IGNORE_BLOCK_END,
            block=IGNORE_BLOCK,
        )
    elif session_log_policy is SessionLogPolicy.TRACKED and ignore_content is not None:
        rendered_ignore = _render_managed_block(
            ignore_content,
            start=IGNORE_BLOCK_START,
            end=IGNORE_BLOCK_END,
            block=None,
        )

    planned_contents: dict[Path, str] = {
        protocol_path: SESSION_PROTOCOL,
        **rendered_instructions,
    }
    if session_log_content is None:
        planned_contents[session_log_path] = ""
    if (
        session_log_policy is not SessionLogPolicy.UNMANAGED
        and rendered_ignore is not None
    ):
        planned_contents[ignore_path] = rendered_ignore

    changed_paths = _apply_planned_contents(planned_contents)

    return InitResult(
        repo_path=repo_path,
        session_log_policy=session_log_policy,
        changed_paths=changed_paths,
    )
