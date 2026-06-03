from pathlib import Path

import pytest

from agentops.core.session import SessionTrace, VerificationRecord
from agentops.parsers.transcript import (
    MAX_FIELD_CHARS,
    MAX_LIST_ITEMS,
    MAX_TASK_BYTES,
    MAX_TASKS,
    TranscriptParseError,
    TranscriptParser,
)

VALID_TASK = """## Task: Fix login error

### Goal
Return 401 for expired tokens.

### Context Used
- `src/auth.py`
- `tests/test_auth.py`

### Changes
- Adjust expired-token mapping.

### Verification
- Command: `python -m pytest tests/test_auth.py -v`
- Result: `3 passed`

### Issues
- First run returned 500.

### Evidence References
- Transcript: `evt_018-evt_031`
"""

MINIMAL_TASK = """## Task: {title}

### Goal
{title} goal.

### Changes
- change

### Verification
- Command: `run`
- Result: `ok`
"""


def _session_file(tmp_path: Path, body: str) -> Path:
    """把任务日志写入 .agentops/agentops-session.md 并返回其路径。"""

    path = tmp_path / ".agentops" / "agentops-session.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_transcript_parser_parses_valid_task(tmp_path: Path) -> None:
    trace = TranscriptParser().parse(_session_file(tmp_path, VALID_TASK))

    assert isinstance(trace, SessionTrace)
    assert trace.truncated is False
    assert len(trace.tasks) == 1
    task = trace.tasks[0]
    assert task.title == "Fix login error"
    assert task.goal == "Return 401 for expired tokens."
    assert task.context_used == ("src/auth.py", "tests/test_auth.py")
    assert task.changes == ("Adjust expired-token mapping.",)
    assert task.verification[0] == VerificationRecord(
        command="python -m pytest tests/test_auth.py -v",
        result="3 passed",
    )
    assert task.issues == ("First run returned 500.",)
    assert task.evidence_references == ("Transcript: `evt_018-evt_031`",)
    assert task.truncated is False


def test_transcript_parser_parses_changed_files(tmp_path: Path) -> None:
    body = (
        "## Task: T\n\n### Goal\ng\n\n"
        "### Changes\n- adjust auth\n\n"
        "### Changed Files\n- `src/auth.py`\n- `tests/test_auth.py`\n\n"
        "### Verification\n- Command: `run`\n- Result: `ok`\n"
    )

    trace = TranscriptParser().parse(_session_file(tmp_path, body))

    # 显式声明的改动路径应按源顺序解析，并剥掉包裹的反引号。
    assert trace.tasks[0].changed_files == ("src/auth.py", "tests/test_auth.py")


def test_transcript_parser_changed_files_optional(tmp_path: Path) -> None:
    # 没有 Changed Files 段时，字段保持空元组（向前兼容旧日志）。
    trace = TranscriptParser().parse(_session_file(tmp_path, VALID_TASK))

    assert trace.tasks[0].changed_files == ()


def test_transcript_parser_preserves_multiple_task_order(tmp_path: Path) -> None:
    body = "\n".join(MINIMAL_TASK.format(title=f"T{index}") for index in range(3))

    trace = TranscriptParser().parse(_session_file(tmp_path, body))

    assert [task.title for task in trace.tasks] == ["T0", "T1", "T2"]


def test_transcript_parser_rejects_missing_title(tmp_path: Path) -> None:
    body = "## Task:\n\n### Goal\ng\n\n### Changes\n- c\n\n### Verification\n- Command: `x`\n- Result: `ok`\n"

    with pytest.raises(TranscriptParseError, match="missing a title"):
        TranscriptParser().parse(_session_file(tmp_path, body))


def test_transcript_parser_rejects_duplicate_section(tmp_path: Path) -> None:
    body = (
        "## Task: T\n\n### Goal\ng\n\n### Goal\ng2\n\n"
        "### Changes\n- c\n\n### Verification\n- Command: `x`\n- Result: `ok`\n"
    )

    with pytest.raises(TranscriptParseError, match="duplicate 'Goal' section"):
        TranscriptParser().parse(_session_file(tmp_path, body))


def test_transcript_parser_rejects_missing_goal(tmp_path: Path) -> None:
    body = "## Task: T\n\n### Changes\n- c\n\n### Verification\n- Command: `x`\n- Result: `ok`\n"

    with pytest.raises(TranscriptParseError, match="missing required section: Goal"):
        TranscriptParser().parse(_session_file(tmp_path, body))


def test_transcript_parser_rejects_missing_changes(tmp_path: Path) -> None:
    body = "## Task: T\n\n### Goal\ng\n\n### Verification\n- Command: `x`\n- Result: `ok`\n"

    with pytest.raises(TranscriptParseError, match="missing required section: Changes"):
        TranscriptParser().parse(_session_file(tmp_path, body))


def test_transcript_parser_rejects_missing_verification(tmp_path: Path) -> None:
    body = "## Task: T\n\n### Goal\ng\n\n### Changes\n- c\n"

    with pytest.raises(
        TranscriptParseError, match="missing required section: Verification"
    ):
        TranscriptParser().parse(_session_file(tmp_path, body))


def test_transcript_parser_rejects_result_without_command(tmp_path: Path) -> None:
    body = "## Task: T\n\n### Goal\ng\n\n### Changes\n- c\n\n### Verification\n- Result: `ok`\n"

    with pytest.raises(
        TranscriptParseError, match="Result without a preceding Command"
    ):
        TranscriptParser().parse(_session_file(tmp_path, body))


def test_transcript_parser_rejects_command_without_result(tmp_path: Path) -> None:
    body = "## Task: T\n\n### Goal\ng\n\n### Changes\n- c\n\n### Verification\n- Command: `x`\n"

    with pytest.raises(
        TranscriptParseError, match="Command without a following Result"
    ):
        TranscriptParser().parse(_session_file(tmp_path, body))


def test_transcript_parser_retains_newest_tasks(tmp_path: Path) -> None:
    total = MAX_TASKS + 50
    body = "\n".join(MINIMAL_TASK.format(title=f"T{index}") for index in range(total))

    trace = TranscriptParser().parse(_session_file(tmp_path, body))

    assert trace.truncated is True
    assert len(trace.tasks) == MAX_TASKS
    # 保留最新的 MAX_TASKS 条，并维持源顺序。
    assert trace.tasks[0].title == "T50"
    assert trace.tasks[-1].title == f"T{total - 1}"


def test_transcript_parser_clips_oversized_free_text(tmp_path: Path) -> None:
    long_goal = "g" * (MAX_FIELD_CHARS + 500)
    body = (
        f"## Task: T\n\n### Goal\n{long_goal}\n\n"
        "### Changes\n- c\n\n### Verification\n- Command: `x`\n- Result: `ok`\n"
    )

    trace = TranscriptParser().parse(_session_file(tmp_path, body))

    assert len(trace.tasks[0].goal) == MAX_FIELD_CHARS
    assert trace.tasks[0].truncated is True


def test_transcript_parser_clips_oversized_list(tmp_path: Path) -> None:
    changes = "\n".join(f"- change {index}" for index in range(MAX_LIST_ITEMS + 10))
    body = (
        "## Task: T\n\n### Goal\ng\n\n"
        f"### Changes\n{changes}\n\n### Verification\n- Command: `x`\n- Result: `ok`\n"
    )

    trace = TranscriptParser().parse(_session_file(tmp_path, body))

    assert len(trace.tasks[0].changes) == MAX_LIST_ITEMS
    assert trace.tasks[0].truncated is True


def test_transcript_parser_rejects_oversized_task(tmp_path: Path) -> None:
    huge_goal = "g" * (MAX_TASK_BYTES + 1_000)
    body = (
        f"## Task: T\n\n### Goal\n{huge_goal}\n\n"
        "### Changes\n- c\n\n### Verification\n- Command: `x`\n- Result: `ok`\n"
    )

    with pytest.raises(TranscriptParseError, match="task report exceeds maximum size"):
        TranscriptParser().parse(_session_file(tmp_path, body))


def test_transcript_parser_reads_incrementally_without_whole_file_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _session_file(tmp_path, VALID_TASK)
    # 同目录下放一个大体量原始 transcript 文件，解析不应读取它。
    raw = tmp_path / ".agentops" / "raw-transcript.txt"
    raw.write_text("RAW-CONTENT " * 5_000, encoding="utf-8")

    def _forbidden(self: Path, *args: object, **kwargs: object) -> str:
        raise AssertionError(f"unexpected whole-file read_text: {self}")

    monkeypatch.setattr(Path, "read_text", _forbidden)

    trace = TranscriptParser().parse(session)

    assert len(trace.tasks) == 1
    # 原始 transcript 内容不应进入任何字段（只保留不透明指针）。
    assert "RAW-CONTENT" not in trace.tasks[0].goal
    for reference in trace.tasks[0].evidence_references:
        assert "RAW-CONTENT" not in reference
