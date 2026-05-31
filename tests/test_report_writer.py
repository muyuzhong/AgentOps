import json
from pathlib import Path

from agentops.core.evaluation import ReadinessReport
from agentops.core.repo import RepoProfile
from agentops.writers.report import ReportWriter


def test_report_writer_writes_markdown_and_json_artifacts(tmp_path: Path) -> None:
    report = ReadinessReport(
        profile=RepoProfile(
            root=Path("demo"),
            has_readme=True,
            constraint_files=("AGENTS.md",),
            test_directories=("tests",),
            ci_files=(".github/workflows/ci.yml",),
            project_markers=("pyproject.toml",),
            test_commands=("python -m pytest",),
        ),
        score=100,
    )
    output_dir = tmp_path / "output"

    artifacts = ReportWriter().write(report, output_dir)

    markdown_path = output_dir / "agentops-report.md"
    json_path = output_dir / "agentops-score.json"
    assert markdown_path.exists()
    assert json_path.exists()
    assert [item.kind.value for item in artifacts] == [
        "markdown_report",
        "json_score",
    ]
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# AgentOps Repository Readiness Report" in markdown
    assert "Score: 100/100" in markdown
    assert "python -m pytest" in markdown
    assert json.loads(json_path.read_text(encoding="utf-8"))["score"] == 100
