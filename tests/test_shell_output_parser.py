from agentops.core.evidence import ShellResult, TestResult
from agentops.parsers.shell_output import (
    MAX_SHELL_SUMMARY_CHARS,
    TRUNCATION_MARKER,
    ShellOutputParser,
)


def test_shell_output_parser_reports_failure_summary() -> None:
    result = ShellOutputParser().parse(
        command="python -m pytest -v",
        exit_code=1,
        stdout="",
        stderr="AssertionError: expected 200, got 500",
    )

    assert isinstance(result, ShellResult)
    assert result.command == "python -m pytest -v"
    assert result.exit_code == 1
    assert result.succeeded is False
    assert "AssertionError" in result.summary
    assert result.truncated is False


def test_shell_output_parser_reports_success_from_exit_code() -> None:
    result = ShellOutputParser().parse(
        command="echo ok",
        exit_code=0,
        stdout="ok",
        stderr="",
    )

    assert result.succeeded is True
    assert result.summary == "ok"


def test_shell_output_parser_labels_both_streams() -> None:
    result = ShellOutputParser().parse(
        command="run",
        exit_code=0,
        stdout="standard output",
        stderr="standard error",
    )

    assert "[stdout]" in result.summary
    assert "standard output" in result.summary
    assert "[stderr]" in result.summary
    assert "standard error" in result.summary


def test_shell_output_parser_bounds_oversized_output() -> None:
    stdout = "FIRST_LINE\n" + ("x" * (MAX_SHELL_SUMMARY_CHARS * 3)) + "\nLAST_LINE"

    result = ShellOutputParser().parse(
        command="run",
        exit_code=0,
        stdout=stdout,
        stderr="",
    )

    assert result.truncated is True
    # 截断后保留首尾，便于看到第一条诊断和最终汇总。
    assert "FIRST_LINE" in result.summary
    assert "LAST_LINE" in result.summary
    assert TRUNCATION_MARKER in result.summary
    # 永远不超过文档约定上限加上标记长度。
    assert len(result.summary) <= MAX_SHELL_SUMMARY_CHARS + len(TRUNCATION_MARKER)


def test_shell_output_parser_recognizes_passed_summary() -> None:
    result = ShellOutputParser().parse(
        command="python -m pytest",
        exit_code=0,
        stdout="===== 3 passed in 0.12s =====",
        stderr="",
    )

    assert result.test_result == TestResult(
        framework="pytest",
        passed=3,
        failed=0,
        skipped=0,
        errors=0,
        succeeded=True,
    )


def test_shell_output_parser_recognizes_mixed_summary() -> None:
    result = ShellOutputParser().parse(
        command="python -m pytest",
        exit_code=1,
        stdout="===== 2 failed, 3 passed, 1 skipped in 0.44s =====",
        stderr="",
    )

    assert result.test_result == TestResult(
        framework="pytest",
        passed=3,
        failed=2,
        skipped=1,
        errors=0,
        succeeded=False,
    )


def test_shell_output_parser_recognizes_error_summary() -> None:
    result = ShellOutputParser().parse(
        command="python -m pytest",
        exit_code=1,
        stdout="1 error in 0.08s",
        stderr="",
    )

    assert result.test_result == TestResult(
        framework="pytest",
        passed=0,
        failed=0,
        skipped=0,
        errors=1,
        succeeded=False,
    )


def test_shell_output_parser_keeps_unknown_output_unknown() -> None:
    result = ShellOutputParser().parse(
        command="make build",
        exit_code=0,
        stdout="Build finished successfully",
        stderr="",
    )

    assert result.test_result is None


def test_shell_output_parser_ignores_summary_without_counts() -> None:
    result = ShellOutputParser().parse(
        command="python -m pytest",
        exit_code=5,
        stdout="no tests ran in 0.01s",
        stderr="",
    )

    assert result.test_result is None
