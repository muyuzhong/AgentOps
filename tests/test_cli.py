from pathlib import Path

import pytest

from agentops.cli import build_parser, main


def test_cli_parser_has_program_description() -> None:
    parser = build_parser()

    assert parser.prog == "agentops"
    assert "AI coding" in parser.description


def test_cli_main_accepts_no_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage: agentops" in capsys.readouterr().out


def test_cli_version_prints_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == "0.1.0"


def test_cli_rejects_phase_one_scan_command() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["scan"])

    assert exc_info.value.code == 2


def test_scan_command_writes_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "README.md").write_text("# Demo", encoding="utf-8")
    output_dir = tmp_path / "output"

    exit_code = main(
        [
            "scan",
            "--repo",
            str(repo_path),
            "--output",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "agentops-report.md").exists()
    assert (output_dir / "agentops-score.json").exists()
    output = capsys.readouterr().out
    assert "AgentOps readiness score:" in output
    assert "Wrote" in output
