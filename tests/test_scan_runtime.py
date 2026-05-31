from pathlib import Path

from agentops.runtime.scan import run_scan


def tree_snapshot(root: Path) -> tuple[tuple[str, bytes | None], ...]:
    return tuple(
        sorted(
            (
                path.relative_to(root).as_posix(),
                None if path.is_dir() else path.read_bytes(),
            )
            for path in root.rglob("*")
        )
    )


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


def test_run_scan_keeps_target_repository_read_only_and_output_stable(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "README.md").write_text("# 演示仓库", encoding="utf-8")
    output_dir = tmp_path / "output"
    before_tree = tree_snapshot(repo_path)

    run_scan(repo_path, output_dir)
    first_markdown = (output_dir / "agentops-report.md").read_bytes()
    first_json = (output_dir / "agentops-score.json").read_bytes()
    run_scan(repo_path, output_dir)

    assert tree_snapshot(repo_path) == before_tree
    assert (output_dir / "agentops-report.md").read_bytes() == first_markdown
    assert (output_dir / "agentops-score.json").read_bytes() == first_json
