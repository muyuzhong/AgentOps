from pathlib import Path

import pytest

from agentops.scanners.repo import RepoScanner


def test_repo_scanner_collects_known_repository_facts(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "README.md").write_text("# Demo", encoding="utf-8")
    (repo_path / "AGENTS.md").write_text("# Instructions", encoding="utf-8")
    (repo_path / "tests").mkdir()
    workflows_path = repo_path / ".github" / "workflows"
    workflows_path.mkdir(parents=True)
    (workflows_path / "ci.yml").write_text("name: CI", encoding="utf-8")
    (repo_path / "pyproject.toml").write_text("[project]", encoding="utf-8")

    profile = RepoScanner().scan(repo_path)

    assert profile.has_readme is True
    assert profile.constraint_files == ("AGENTS.md",)
    assert profile.test_directories == ("tests",)
    assert profile.ci_files == (".github/workflows/ci.yml",)
    assert profile.project_markers == ("pyproject.toml",)
    assert profile.test_commands == ("python -m pytest",)


def test_repo_scanner_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="repository directory does not exist"):
        RepoScanner().scan(tmp_path / "missing")


def test_repo_scanner_does_not_count_directories_as_files(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "README.md").mkdir()
    (repo_path / "AGENTS.md").mkdir()
    (repo_path / "pyproject.toml").mkdir()
    (repo_path / ".gitlab-ci.yml").mkdir()
    workflows_path = repo_path / ".github" / "workflows"
    workflows_path.mkdir(parents=True)
    (workflows_path / "fake.yml").mkdir()

    profile = RepoScanner().scan(repo_path)

    assert profile.has_readme is False
    assert profile.constraint_files == ()
    assert profile.project_markers == ()
    assert profile.test_commands == ()
    assert profile.ci_files == ()


def test_repo_scanner_collects_validation_commands(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    workflows_path = repo_path / ".github" / "workflows"
    workflows_path.mkdir(parents=True)
    (workflows_path / "ci.yml").write_text(
        "\n".join(
            [
                "jobs:",
                "  build:",
                "    steps:",
                "      - run: python -m pytest",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    profile = RepoScanner().scan(repo_path)

    assert profile.ci_files == (".github/workflows/ci.yml",)
    assert profile.validation_commands == ("python -m pytest",)
