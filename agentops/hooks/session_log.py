"""会话日志新鲜度检查：判断 agent 停止前是否追加了新的任务汇报。

这是"声明链路"的可靠性基础——如果 agent 不写声明，后续的"声明 vs 真相"
对账就无从谈起。本检查是确定性的，只读取有界的任务日志，并仅在自己的状态
文件（`.agentops/.session-log-state.json`）上产生副作用。
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from agentops.parsers.transcript import TranscriptParseError, TranscriptParser

# 任务日志与状态文件相对仓库根目录的位置。
SESSION_LOG_RELATIVE = (".agentops", "agentops-session.md")
STATE_RELATIVE = (".agentops", ".session-log-state.json")

# 未检测到新追加时输出的提醒。
REMINDER = (
    "尚未检测到新的任务汇报。请在每个独立开发任务完成后，"
    "按 `.agentops/session-protocol.md` 的格式向 `.agentops/agentops-session.md` 追加简短汇报。"
)


@dataclass(frozen=True)
class SessionLogState:
    """记录某一时刻任务日志的指纹。"""

    byte_size: int
    sha256: str
    task_count: int

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 友好结构。"""

        return {
            "byte_size": self.byte_size,
            "sha256": self.sha256,
            "task_count": self.task_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionLogState | None":
        """从持久化状态恢复；结构不符时返回 None。"""

        try:
            return cls(
                byte_size=int(data["byte_size"]),
                sha256=str(data["sha256"]),
                task_count=int(data["task_count"]),
            )
        except (KeyError, TypeError, ValueError):
            return None


@dataclass(frozen=True)
class SessionLogCheck:
    """一次新鲜度检查的结果。"""

    has_new_content: bool
    previous: SessionLogState | None
    current: SessionLogState
    reminder: str | None


def check_session_log(repo_path: Path) -> SessionLogCheck:
    """对比任务日志与上次记录的状态，判断是否有新追加，并刷新基线。"""

    repo_path = Path(repo_path)
    log_path = repo_path.joinpath(*SESSION_LOG_RELATIVE)
    state_path = repo_path.joinpath(*STATE_RELATIVE)

    previous = _load_state(state_path)
    current = _current_state(log_path)

    # 只有"字节变多且内容指纹改变"时才认定有新追加；缺少基线一律提醒。
    has_new_content = (
        previous is not None
        and current.byte_size > previous.byte_size
        and current.sha256 != previous.sha256
    )
    reminder = None if has_new_content else REMINDER

    # 总是记录当前状态，作为下次检查的基线。
    _save_state(state_path, current)

    return SessionLogCheck(
        has_new_content=has_new_content,
        previous=previous,
        current=current,
        reminder=reminder,
    )


def _current_state(log_path: Path) -> SessionLogState:
    """计算任务日志当前的指纹；文件缺失时退化为空状态。"""

    if not log_path.is_file():
        empty_digest = hashlib.sha256(b"").hexdigest()
        return SessionLogState(byte_size=0, sha256=empty_digest, task_count=0)
    raw = log_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    return SessionLogState(
        byte_size=len(raw),
        sha256=digest,
        task_count=_safe_task_count(log_path),
    )


def _safe_task_count(log_path: Path) -> int:
    """用有界 TranscriptParser 统计任务数；日志不合法时记为 0，不让检查崩溃。"""

    try:
        return len(TranscriptParser().parse(log_path).tasks)
    except (TranscriptParseError, UnicodeDecodeError, OSError):
        return 0


def _load_state(state_path: Path) -> SessionLogState | None:
    """读取上次记录的状态；缺失或损坏时返回 None。"""

    if not state_path.is_file():
        return None
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return SessionLogState.from_dict(data)


def _save_state(state_path: Path, state: SessionLogState) -> None:
    """原子写入状态文件，避免中断留下半个文件。"""

    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=state_path.parent,
            prefix=".session-log-state.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(payload)
        os.replace(temporary_path, state_path)
    except Exception:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
        raise
