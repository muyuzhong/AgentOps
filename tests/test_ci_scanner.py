from pathlib import Path

import pytest

from agentops.core.evidence import CIProfile
from agentops.scanners.ci import CIDetector, CIScanError


def _write(path: Path, text: str) -> None:
    """写入 UTF-8 文本并确保父目录存在。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_ci_detector_collects_sorted_config_files(tmp_path: Path) -> None:
    _write(tmp_path / ".gitlab-ci.yml", "stages: [test]\n")
    _write(tmp_path / "azure-pipelines.yml", "steps: []\n")
    _write(tmp_path / ".github" / "workflows" / "ci.yml", "name: CI\n")
    _write(tmp_path / ".github" / "workflows" / "release.yaml", "name: Release\n")

    profile = CIDetector().scan(tmp_path)

    assert isinstance(profile, CIProfile)
    assert profile.config_files == (
        ".github/workflows/ci.yml",
        ".github/workflows/release.yaml",
        ".gitlab-ci.yml",
        "azure-pipelines.yml",
    )


def test_ci_detector_ignores_directories(tmp_path: Path) -> None:
    (tmp_path / ".gitlab-ci.yml").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "fake.yml").mkdir()

    profile = CIDetector().scan(tmp_path)

    assert profile.config_files == ()
    assert profile.validation_commands == ()


def test_ci_detector_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="repository directory does not exist"):
        CIDetector().scan(tmp_path / "missing")


def test_ci_detector_raises_on_malformed_yaml(tmp_path: Path) -> None:
    _write(tmp_path / ".gitlab-ci.yml", "script: [unterminated\n")

    with pytest.raises(
        CIScanError,
        match="could not parse CI configuration file: .gitlab-ci.yml",
    ):
        CIDetector().scan(tmp_path)


def test_ci_detector_extracts_github_run_commands(tmp_path: Path) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "\n".join(
            [
                "name: CI",
                "on: [push]",
                "jobs:",
                "  build:",
                "    steps:",
                "      - uses: actions/checkout@v4",
                "      - run: pip install -e .",
                "      - run: |",
                "          python -m pytest",
                "          ruff check .",
            ]
        )
        + "\n",
    )

    profile = CIDetector().scan(tmp_path)

    assert profile.validation_commands == (
        "pip install -e .",
        "python -m pytest",
        "ruff check .",
    )


def test_ci_detector_extracts_gitlab_scripts(tmp_path: Path) -> None:
    _write(
        tmp_path / ".gitlab-ci.yml",
        "\n".join(
            [
                "before_script:",
                "  - pip install -e .",
                "test:",
                "  script:",
                "    - python -m pytest",
                "  after_script:",
                "    - echo done",
            ]
        )
        + "\n",
    )

    profile = CIDetector().scan(tmp_path)

    assert profile.validation_commands == (
        "pip install -e .",
        "python -m pytest",
        "echo done",
    )


def test_ci_detector_extracts_azure_step_commands(tmp_path: Path) -> None:
    _write(
        tmp_path / "azure-pipelines.yml",
        "\n".join(
            [
                "steps:",
                "  - script: pip install -e .",
                "  - bash: ./scripts/test.sh",
                "jobs:",
                "  - job: Build",
                "    steps:",
                "      - powershell: Write-Host hi",
            ]
        )
        + "\n",
    )

    profile = CIDetector().scan(tmp_path)

    assert profile.validation_commands == (
        "pip install -e .",
        "./scripts/test.sh",
        "Write-Host hi",
    )


def test_ci_detector_deduplicates_preserving_first_seen_order(tmp_path: Path) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "\n".join(
            [
                "jobs:",
                "  a:",
                "    steps:",
                "      - run: python -m pytest",
                "  b:",
                "    steps:",
                "      - run: python -m pytest",
                "      - run: ruff check .",
            ]
        )
        + "\n",
    )

    profile = CIDetector().scan(tmp_path)

    assert profile.validation_commands == ("python -m pytest", "ruff check .")


def test_ci_detector_returns_empty_profile_without_ci(tmp_path: Path) -> None:
    profile = CIDetector().scan(tmp_path)

    assert profile.config_files == ()
    assert profile.validation_commands == ()
