from pathlib import Path

import pytest

import agentops.initializers.repo as repo_initializer
from agentops.initializers.repo import (
    IGNORE_BLOCK_END,
    IGNORE_BLOCK_START,
    INSTRUCTION_BLOCK,
    INSTRUCTION_BLOCK_END,
    INSTRUCTION_BLOCK_START,
    SESSION_PROTOCOL,
    InitResult,
    SessionLogPolicy,
    run_init,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_run_init_rejects_missing_repository_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="repository path must be an existing directory"):
        run_init(tmp_path / "missing", SessionLogPolicy.PRIVATE)


def test_run_init_creates_protocol_session_log_rule_and_private_ignore(
    tmp_path: Path,
) -> None:
    result = run_init(tmp_path, SessionLogPolicy.PRIVATE)

    assert result == InitResult(
        repo_path=tmp_path,
        session_log_policy=SessionLogPolicy.PRIVATE,
        changed_paths=tuple(sorted(result.changed_paths)),
    )
    assert result.changed_paths == tuple(
        sorted(
            (
                tmp_path / ".agentops" / ".gitignore",
                tmp_path / ".agentops" / "agentops-session.md",
                tmp_path / ".agentops" / "session-protocol.md",
                tmp_path / "rule.md",
            )
        )
    )
    assert _read(tmp_path / ".agentops" / "session-protocol.md") == SESSION_PROTOCOL
    assert _read(tmp_path / ".agentops" / "agentops-session.md") == ""
    assert _read(tmp_path / "rule.md") == INSTRUCTION_BLOCK
    assert _read(tmp_path / ".agentops" / ".gitignore") == (
        f"{IGNORE_BLOCK_START}\n"
        "agentops-session.md\n"
        f"{IGNORE_BLOCK_END}\n"
    )


def test_run_init_preserves_existing_session_log_content(tmp_path: Path) -> None:
    session_log = tmp_path / ".agentops" / "agentops-session.md"
    _write(session_log, "## Task: Existing\n")

    result = run_init(tmp_path, SessionLogPolicy.PRIVATE)

    assert _read(session_log) == "## Task: Existing\n"
    assert session_log not in result.changed_paths


def test_run_init_refreshes_existing_protocol_content(tmp_path: Path) -> None:
    protocol = tmp_path / ".agentops" / "session-protocol.md"
    _write(protocol, "# Old protocol\n")

    result = run_init(tmp_path, SessionLogPolicy.UNMANAGED)

    assert _read(protocol) == SESSION_PROTOCOL
    assert protocol in result.changed_paths


@pytest.mark.parametrize(
    ("filenames", "expected_names"),
    [
        (("CLAUDE.md",), ("CLAUDE.md",)),
        (("AGENTS.md",), ("AGENTS.md",)),
        (("CLAUDE.md", "AGENTS.md"), ("AGENTS.md", "CLAUDE.md")),
    ],
)
def test_run_init_updates_existing_instruction_files_without_creating_rule(
    tmp_path: Path,
    filenames: tuple[str, ...],
    expected_names: tuple[str, ...],
) -> None:
    for filename in filenames:
        _write(tmp_path / filename, f"# Existing {filename}\n")

    run_init(tmp_path, SessionLogPolicy.UNMANAGED)

    assert not (tmp_path / "rule.md").exists()
    for filename in expected_names:
        content = _read(tmp_path / filename)
        assert content.startswith(f"# Existing {filename}\n")
        assert content.count(INSTRUCTION_BLOCK_START) == 1
        assert content.count(INSTRUCTION_BLOCK_END) == 1


def test_run_init_preserves_existing_fallback_rule_content(tmp_path: Path) -> None:
    _write(tmp_path / "rule.md", "# Existing fallback rules\n")

    run_init(tmp_path, SessionLogPolicy.UNMANAGED)

    assert _read(tmp_path / "rule.md").startswith("# Existing fallback rules\n")


def test_run_init_is_idempotent_and_collapses_duplicate_instruction_blocks(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "CLAUDE.md",
        f"# Before\n\n{INSTRUCTION_BLOCK}\n{INSTRUCTION_BLOCK}\n# After\n",
    )

    first = run_init(tmp_path, SessionLogPolicy.PRIVATE)
    second = run_init(tmp_path, SessionLogPolicy.PRIVATE)

    content = _read(tmp_path / "CLAUDE.md")
    assert content.startswith("# Before\n")
    assert content.endswith("# After\n")
    assert content.count(INSTRUCTION_BLOCK_START) == 1
    assert content.count(INSTRUCTION_BLOCK_END) == 1
    assert first.changed_paths
    assert second.changed_paths == ()


def test_run_init_does_not_replace_inline_marker_examples(tmp_path: Path) -> None:
    instruction = tmp_path / "CLAUDE.md"
    original = (
        "# Marker example\n"
        f"Use `{INSTRUCTION_BLOCK_START}` and `{INSTRUCTION_BLOCK_END}` as delimiters.\n"
    )
    _write(instruction, original)

    run_init(tmp_path, SessionLogPolicy.UNMANAGED)

    assert _read(instruction).startswith(original)
    assert _read(instruction).endswith(INSTRUCTION_BLOCK)


def test_run_init_preserves_crlf_instruction_content(tmp_path: Path) -> None:
    instruction = tmp_path / "CLAUDE.md"
    original = b"# Existing rules\r\n- keep this line\r\n"
    _write_bytes(instruction, original)

    run_init(tmp_path, SessionLogPolicy.UNMANAGED)

    content = instruction.read_bytes()
    assert content.startswith(original)
    assert b"\n" not in content.replace(b"\r\n", b"")


def test_private_policy_preserves_unrelated_ignore_rules_and_collapses_duplicates(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".agentops" / ".gitignore",
        (
            "custom.cache\n"
            f"{IGNORE_BLOCK_START}\nagentops-session.md\n{IGNORE_BLOCK_END}\n"
            f"{IGNORE_BLOCK_START}\nagentops-session.md\n{IGNORE_BLOCK_END}\n"
            "notes.txt\n"
        ),
    )

    run_init(tmp_path, SessionLogPolicy.PRIVATE)

    content = _read(tmp_path / ".agentops" / ".gitignore")
    assert "custom.cache\n" in content
    assert "notes.txt\n" in content
    assert content.count(IGNORE_BLOCK_START) == 1
    assert content.count(IGNORE_BLOCK_END) == 1


def test_private_policy_preserves_crlf_ignore_content(tmp_path: Path) -> None:
    agentops_ignore = tmp_path / ".agentops" / ".gitignore"
    original = b"custom.cache\r\nnotes.txt\r\n"
    _write_bytes(agentops_ignore, original)

    run_init(tmp_path, SessionLogPolicy.PRIVATE)

    content = agentops_ignore.read_bytes()
    assert content.startswith(original)
    assert b"\n" not in content.replace(b"\r\n", b"")


def test_tracked_policy_removes_only_managed_ignore_block(tmp_path: Path) -> None:
    root_ignore = tmp_path / ".gitignore"
    agentops_ignore = tmp_path / ".agentops" / ".gitignore"
    _write(root_ignore, ".agentops/\n")
    _write(
        agentops_ignore,
        f"custom.cache\n{IGNORE_BLOCK_START}\nagentops-session.md\n{IGNORE_BLOCK_END}\n",
    )

    run_init(tmp_path, SessionLogPolicy.TRACKED)

    assert _read(root_ignore) == ".agentops/\n"
    assert _read(agentops_ignore) == "custom.cache\n"


def test_tracked_policy_leaves_empty_ignore_when_only_managed_block_exists(
    tmp_path: Path,
) -> None:
    agentops_ignore = tmp_path / ".agentops" / ".gitignore"
    _write(
        agentops_ignore,
        f"{IGNORE_BLOCK_START}\nagentops-session.md\n{IGNORE_BLOCK_END}\n",
    )

    run_init(tmp_path, SessionLogPolicy.TRACKED)

    assert _read(agentops_ignore) == ""


def test_tracked_policy_preserves_crlf_unrelated_ignore_content(tmp_path: Path) -> None:
    agentops_ignore = tmp_path / ".agentops" / ".gitignore"
    original = (
        b"custom.cache\r\n"
        + IGNORE_BLOCK_START.encode("utf-8")
        + b"\r\nagentops-session.md\r\n"
        + IGNORE_BLOCK_END.encode("utf-8")
        + b"\r\nnotes.txt\r\n"
    )
    _write_bytes(agentops_ignore, original)

    run_init(tmp_path, SessionLogPolicy.TRACKED)

    assert agentops_ignore.read_bytes() == b"custom.cache\r\nnotes.txt\r\n"


def test_unmanaged_policy_does_not_modify_agentops_ignore(tmp_path: Path) -> None:
    agentops_ignore = tmp_path / ".agentops" / ".gitignore"
    original = (
        f"custom.cache\n{IGNORE_BLOCK_START}\nagentops-session.md\n{IGNORE_BLOCK_END}\n"
    )
    _write(agentops_ignore, original)

    result = run_init(tmp_path, SessionLogPolicy.UNMANAGED)

    assert _read(agentops_ignore) == original
    assert agentops_ignore not in result.changed_paths


@pytest.mark.parametrize(
    "policy",
    [SessionLogPolicy.TRACKED, SessionLogPolicy.UNMANAGED],
)
def test_non_private_policy_does_not_create_agentops_ignore(
    tmp_path: Path,
    policy: SessionLogPolicy,
) -> None:
    result = run_init(tmp_path, policy)

    agentops_ignore = tmp_path / ".agentops" / ".gitignore"
    assert not agentops_ignore.exists()
    assert agentops_ignore not in result.changed_paths


def test_run_init_rejects_malformed_instruction_markers_without_writing(
    tmp_path: Path,
) -> None:
    instruction = tmp_path / "CLAUDE.md"
    original = f"# Rules\n{INSTRUCTION_BLOCK_START}\n"
    _write(instruction, original)

    with pytest.raises(ValueError, match="managed block markers are malformed"):
        run_init(tmp_path, SessionLogPolicy.PRIVATE)

    assert _read(instruction) == original
    assert not (tmp_path / ".agentops").exists()


def test_run_init_rejects_malformed_ignore_markers_without_rewriting_files(
    tmp_path: Path,
) -> None:
    instruction = tmp_path / "CLAUDE.md"
    agentops_ignore = tmp_path / ".agentops" / ".gitignore"
    instruction_original = "# Existing rules\n"
    ignore_original = f"custom.cache\n{IGNORE_BLOCK_START}\n"
    _write(instruction, instruction_original)
    _write(agentops_ignore, ignore_original)

    with pytest.raises(ValueError, match="managed block markers are malformed"):
        run_init(tmp_path, SessionLogPolicy.PRIVATE)

    assert _read(instruction) == instruction_original
    assert _read(agentops_ignore) == ignore_original
    assert not (tmp_path / ".agentops" / "session-protocol.md").exists()


def test_run_init_rejects_any_malformed_instruction_before_writing(
    tmp_path: Path,
) -> None:
    claude = tmp_path / "CLAUDE.md"
    agents = tmp_path / "AGENTS.md"
    claude_original = "# Claude rules\n"
    agents_original = f"# Shared rules\n{INSTRUCTION_BLOCK_START}\n"
    _write(claude, claude_original)
    _write(agents, agents_original)

    with pytest.raises(ValueError, match="managed block markers are malformed"):
        run_init(tmp_path, SessionLogPolicy.PRIVATE)

    assert _read(claude) == claude_original
    assert _read(agents) == agents_original
    assert not (tmp_path / ".agentops").exists()


def test_run_init_rejects_instruction_directory_without_writing(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").mkdir()

    with pytest.raises(ValueError, match="instruction path must be a regular file"):
        run_init(tmp_path, SessionLogPolicy.PRIVATE)

    assert not (tmp_path / ".agentops").exists()


def test_run_init_rejects_managed_file_directory_without_writing(tmp_path: Path) -> None:
    agentops_path = tmp_path / ".agentops"
    agentops_path.mkdir()
    (agentops_path / "session-protocol.md").mkdir()

    with pytest.raises(ValueError, match="managed path must be a regular file"):
        run_init(tmp_path, SessionLogPolicy.PRIVATE)

    assert not (tmp_path / "rule.md").exists()
    assert not (agentops_path / "agentops-session.md").exists()


def test_run_init_rolls_back_files_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instruction = tmp_path / "CLAUDE.md"
    original = "# Existing rules\n"
    _write(instruction, original)
    real_replace = repo_initializer._replace_staged

    def fail_instruction_replace(staged_path: Path, destination: Path) -> None:
        if destination == instruction:
            raise OSError("instruction replacement failed")
        real_replace(staged_path, destination)

    monkeypatch.setattr(repo_initializer, "_replace_staged", fail_instruction_replace)

    with pytest.raises(OSError, match="instruction replacement failed"):
        run_init(tmp_path, SessionLogPolicy.PRIVATE)

    assert _read(instruction) == original
    assert not (tmp_path / ".agentops").exists()


def test_run_init_cleans_staged_files_when_staging_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instruction = tmp_path / "CLAUDE.md"
    original = "# Existing rules\n"
    _write(instruction, original)
    real_stage = repo_initializer._stage_write

    def fail_instruction_stage(path: Path, content: str) -> Path:
        if path == instruction:
            raise OSError("instruction staging failed")
        return real_stage(path, content)

    monkeypatch.setattr(repo_initializer, "_stage_write", fail_instruction_stage)

    with pytest.raises(OSError, match="instruction staging failed"):
        run_init(tmp_path, SessionLogPolicy.PRIVATE)

    assert _read(instruction) == original
    assert not (tmp_path / ".agentops").exists()


def test_run_init_cleans_partial_temp_file_when_staged_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_named_temporary_file = repo_initializer.NamedTemporaryFile

    class FailingTemporaryFile:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self._temporary_file = real_named_temporary_file(*args, **kwargs)
            self._handle: object | None = None

        def __enter__(self) -> "FailingTemporaryFile":
            self._handle = self._temporary_file.__enter__()
            return self

        def __exit__(self, *args: object) -> object:
            return self._temporary_file.__exit__(*args)

        @property
        def name(self) -> str:
            assert self._handle is not None
            return self._handle.name

        def write(self, content: str) -> None:
            assert self._handle is not None
            self._handle.write(content[:1])
            raise OSError("temporary file write failed")

    monkeypatch.setattr(
        repo_initializer,
        "NamedTemporaryFile",
        FailingTemporaryFile,
    )

    with pytest.raises(OSError, match="temporary file write failed"):
        run_init(tmp_path, SessionLogPolicy.PRIVATE)

    assert not (tmp_path / ".agentops").exists()
    assert not (tmp_path / "rule.md").exists()
