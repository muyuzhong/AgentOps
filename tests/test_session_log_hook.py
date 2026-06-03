from pathlib import Path

from agentops.hooks.session_log import (
    SessionLogCheck,
    SessionLogState,
    check_session_log,
)

PROTOCOL_TASK = """## Task: {title}

### Goal
g

### Changes
- c

### Verification
- Command: `run`
- Result: `ok`
"""


def _write_log(repo: Path, body: str) -> Path:
    """把任务日志写入 .agentops/agentops-session.md 并返回其路径。"""

    path = repo / ".agentops" / "agentops-session.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_missing_baseline_reminds_and_records_state(tmp_path: Path) -> None:
    _write_log(tmp_path, PROTOCOL_TASK.format(title="T1"))

    result = check_session_log(tmp_path)

    assert isinstance(result, SessionLogCheck)
    assert result.has_new_content is False
    assert result.previous is None
    assert result.reminder is not None
    assert result.current.task_count == 1
    assert result.current.byte_size > 0
    # 状态文件已记录，作为下次基线。
    assert (tmp_path / ".agentops" / ".session-log-state.json").is_file()


def test_detects_new_content(tmp_path: Path) -> None:
    _write_log(tmp_path, PROTOCOL_TASK.format(title="T1"))
    check_session_log(tmp_path)  # 记录基线

    _write_log(
        tmp_path,
        PROTOCOL_TASK.format(title="T1") + "\n" + PROTOCOL_TASK.format(title="T2"),
    )
    result = check_session_log(tmp_path)

    assert result.has_new_content is True
    assert result.reminder is None
    assert result.previous is not None
    assert result.current.byte_size > result.previous.byte_size
    assert result.current.task_count == 2


def test_reminds_when_unchanged(tmp_path: Path) -> None:
    _write_log(tmp_path, PROTOCOL_TASK.format(title="T1"))
    check_session_log(tmp_path)  # 记录基线

    result = check_session_log(tmp_path)  # 内容未变

    assert result.has_new_content is False
    assert result.reminder is not None


def test_missing_log_reminds(tmp_path: Path) -> None:
    (tmp_path / ".agentops").mkdir(parents=True)

    result = check_session_log(tmp_path)

    assert result.has_new_content is False
    assert result.reminder is not None
    assert result.current.byte_size == 0
    assert result.current.task_count == 0


def test_state_serializes_stably(tmp_path: Path) -> None:
    _write_log(tmp_path, PROTOCOL_TASK.format(title="T1"))

    result = check_session_log(tmp_path)

    data = result.current.to_dict()
    assert set(data) == {"byte_size", "sha256", "task_count"}
    assert isinstance(data["sha256"], str)
    assert data["task_count"] == 1


def test_malformed_log_does_not_crash(tmp_path: Path) -> None:
    # 缺少标题与必需章节的非法日志不应让检查崩溃。
    _write_log(tmp_path, "## Task:\n\n(not a valid report)\n")

    result = check_session_log(tmp_path)

    assert result.current.task_count == 0
    assert result.reminder is not None
