from pathlib import Path

from agentops.runtime.scan import run_scan


def test_run_scan_orchestrates_repository_readiness_workflow(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "README.md").write_text("# Demo", encoding="utf-8")
    (repo_path / "AGENTS.md").write_text("# Instructions", encoding="utf-8")
    (repo_path / "tests").mkdir()
    workflows_path = repo_path / ".github" / "workflows"
    workflows_path.mkdir(parents=True)
    (workflows_path / "ci.yml").write_text("name: CI", encoding="utf-8")
    (repo_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
    output_dir = tmp_path / "output"

    result = run_scan(repo_path, output_dir)

    assert result.report.profile.root == repo_path
    assert result.report.score == 100
    assert {item.path.name for item in result.artifacts} == {
        "agentops-report.md",
        "agentops-score.json",
    }
