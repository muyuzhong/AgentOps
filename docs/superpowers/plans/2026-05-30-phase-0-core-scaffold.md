# Phase 0 Core Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the smallest testable Python package for AgentOps Harness with core data models, a minimal CLI, and a clean Git baseline.

**Architecture:** Phase 0 establishes the project's public language before implementing repository scanning. The package uses focused `dataclass` models and the Python standard library. The CLI is deliberately thin and exposes only `--help` and version information; real scanning arrives in Phase 1.

**Tech Stack:** Python 3.11+, standard library `dataclasses`, `argparse`, `pathlib`, `pytest`

---

## Scope Guard

Implement only the scaffold and foundational models.

Do not add:

- Repository scanning logic.
- Session parsing.
- LLM calls.
- Storage or memory.
- Watcher processes.
- Plugin systems.
- Abstract base classes without an immediate caller.

## Target File Structure

```text
agentops_harness/
  .gitignore
  README.md
  pyproject.toml
  agent.md
  docs/
    positioning-and-boundaries.md
  agentops/
    __init__.py
    cli.py
    core/
      __init__.py
      artifact.py
      evaluation.py
      recommendation.py
      repo.py
  tests/
    test_cli.py
    test_core_models.py
```

## Task 1: Create the Git baseline

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Initialize Git**

Run:

```powershell
git init
```

Expected: Git reports an initialized empty repository.

- [ ] **Step 2: Create `.gitignore`**

Add:

```gitignore
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
venv/
dist/
build/
*.egg-info/
.coverage
htmlcov/
.env
.agentops/
```

- [ ] **Step 3: Verify ignored local output**

Run:

```powershell
git status --short
```

Expected: project documents and `.gitignore` appear as untracked files; no Python cache directories appear.

- [ ] **Step 4: Commit the documentation baseline**

Run:

```powershell
git add .gitignore agent.md docs/positioning-and-boundaries.md docs/superpowers/plans
git commit -m "docs: establish agentops harness direction"
```

Expected: one root commit is created.

## Task 2: Add package metadata

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `agentops/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

Use:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "agentops-harness"
version = "0.1.0"
description = "Repository-native AI coding quality evaluation and optimization harness"
readme = "README.md"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
]

[project.scripts]
agentops = "agentops.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `README.md`**

Keep it short. Include:

````markdown
# AgentOps Harness

AgentOps Harness evaluates and improves AI coding work in real repositories.

The first milestone provides a read-only repository readiness scan:

```bash
agentops scan --repo <repo-path>
```

See `agent.md` and `docs/positioning-and-boundaries.md` before development.
````

- [ ] **Step 3: Create package version**

Use:

```python
"""AgentOps Harness package."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Install the editable package**

Run:

```powershell
python -m pip install -e ".[dev]"
```

Expected: installation succeeds and `pytest` is available.

- [ ] **Step 5: Commit package metadata**

Run:

```powershell
git add pyproject.toml README.md agentops/__init__.py
git commit -m "build: add python package metadata"
```

## Task 3: Define repository and recommendation models

**Files:**
- Create: `agentops/core/__init__.py`
- Create: `agentops/core/repo.py`
- Create: `agentops/core/recommendation.py`
- Test: `tests/test_core_models.py`

- [ ] **Step 1: Write failing model tests**

Create tests that require:

```python
from pathlib import Path

from agentops.core.recommendation import Recommendation, RecommendationKind
from agentops.core.repo import RepoProfile


def test_repo_profile_serializes_paths_as_strings() -> None:
    profile = RepoProfile(
        root=Path("demo"),
        has_readme=True,
        constraint_files=("AGENTS.md",),
    )

    assert profile.to_dict()["root"] == "demo"
    assert profile.to_dict()["constraint_files"] == ["AGENTS.md"]


def test_recommendation_exposes_actionable_fields() -> None:
    recommendation = Recommendation(
        kind=RecommendationKind.ADD_CONSTRAINT_FILE,
        title="Add AGENTS.md",
        rationale="The repository has no agent instructions.",
        action="Create an AGENTS.md file with test commands and boundaries.",
    )

    assert recommendation.to_dict()["kind"] == "add_constraint_file"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_core_models.py -v
```

Expected: FAIL because `agentops.core` models do not exist.

- [ ] **Step 3: Implement `RepoProfile`**

Define a small immutable dataclass:

```python
@dataclass(frozen=True)
class RepoProfile:
    root: Path
    has_readme: bool = False
    constraint_files: tuple[str, ...] = ()
    test_directories: tuple[str, ...] = ()
    ci_files: tuple[str, ...] = ()
    project_markers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        ...
```

Use explicit `to_dict()` conversion so JSON-facing behavior is stable.

- [ ] **Step 4: Implement `Recommendation`**

Define:

```python
class RecommendationKind(str, Enum):
    ADD_CONSTRAINT_FILE = "add_constraint_file"
    ADD_README = "add_readme"
    ADD_TESTS = "add_tests"
    ADD_CI = "add_ci"
    REVIEW_TEST_COMMANDS = "review_test_commands"


@dataclass(frozen=True)
class Recommendation:
    kind: RecommendationKind
    title: str
    rationale: str
    action: str

    def to_dict(self) -> dict[str, str]:
        ...
```

- [ ] **Step 5: Export public core types**

Expose `RepoProfile`, `Recommendation`, and `RecommendationKind` from `agentops/core/__init__.py`.

- [ ] **Step 6: Run tests**

Run:

```powershell
python -m pytest tests/test_core_models.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add agentops/core tests/test_core_models.py
git commit -m "feat: define repository and recommendation models"
```

## Task 4: Define evaluation and artifact models

**Files:**
- Create: `agentops/core/evaluation.py`
- Create: `agentops/core/artifact.py`
- Modify: `agentops/core/__init__.py`
- Modify: `tests/test_core_models.py`

- [ ] **Step 1: Add failing tests**

Add tests that require:

```python
from agentops.core.artifact import Artifact, ArtifactKind
from agentops.core.evaluation import Finding, ReadinessReport, Severity


def test_readiness_report_serializes_findings_and_recommendations() -> None:
    report = ReadinessReport(
        profile=RepoProfile(root=Path("demo")),
        score=75,
        findings=(
            Finding(
                code="missing_agents_md",
                severity=Severity.WARNING,
                message="AGENTS.md is missing.",
                evidence=("AGENTS.md",),
            ),
        ),
        recommendations=(),
    )

    data = report.to_dict()
    assert data["score"] == 75
    assert data["findings"][0]["severity"] == "warning"


def test_artifact_serializes_kind_and_path() -> None:
    artifact = Artifact(kind=ArtifactKind.MARKDOWN_REPORT, path=Path("report.md"))

    assert artifact.to_dict() == {
        "kind": "markdown_report",
        "path": "report.md",
    }
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_core_models.py -v
```

Expected: FAIL because evaluation and artifact models do not exist.

- [ ] **Step 3: Implement evaluation models**

Define:

```python
class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    message: str
    evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        ...


@dataclass(frozen=True)
class ReadinessReport:
    profile: RepoProfile
    score: int
    findings: tuple[Finding, ...] = ()
    recommendations: tuple[Recommendation, ...] = ()

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100")

    def to_dict(self) -> dict[str, object]:
        ...
```

- [ ] **Step 4: Implement artifact models**

Define:

```python
class ArtifactKind(str, Enum):
    MARKDOWN_REPORT = "markdown_report"
    JSON_SCORE = "json_score"


@dataclass(frozen=True)
class Artifact:
    kind: ArtifactKind
    path: Path

    def to_dict(self) -> dict[str, str]:
        ...
```

- [ ] **Step 5: Export public core types**

Update `agentops/core/__init__.py`.

- [ ] **Step 6: Run tests**

Run:

```powershell
python -m pytest tests/test_core_models.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add agentops/core tests/test_core_models.py
git commit -m "feat: define readiness report models"
```

## Task 5: Add the minimal CLI

**Files:**
- Create: `agentops/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write a failing CLI test**

Use:

```python
from agentops.cli import build_parser


def test_cli_parser_has_program_description() -> None:
    parser = build_parser()

    assert parser.prog == "agentops"
    assert "AI coding" in parser.description
```

- [ ] **Step 2: Run the test and confirm failure**

Run:

```powershell
python -m pytest tests/test_cli.py -v
```

Expected: FAIL because `agentops.cli` does not exist.

- [ ] **Step 3: Implement the minimal CLI**

Use `argparse`:

```python
from __future__ import annotations

import argparse

from agentops import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentops",
        description="Evaluate and improve AI coding work in real repositories.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    return 0
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest -v
```

Expected: PASS.

- [ ] **Step 5: Verify the installed command**

Run:

```powershell
agentops --help
agentops --version
```

Expected: help text is printed and version is `0.1.0`.

- [ ] **Step 6: Commit**

Run:

```powershell
git add agentops/cli.py tests/test_cli.py
git commit -m "feat: add minimal agentops cli"
```

## Task 6: Verify Phase 0

- [ ] **Step 1: Run the full test suite**

Run:

```powershell
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Inspect the CLI**

Run:

```powershell
agentops --help
```

Expected: command exits with code `0` and prints the package description.

- [ ] **Step 3: Confirm the worktree is clean**

Run:

```powershell
git status --short
```

Expected: no output.

## Exit Criteria

Phase 0 is complete when:

- The project is a Git repository.
- `python -m pip install -e ".[dev]"` succeeds.
- Core models serialize into JSON-ready dictionaries.
- `agentops --help` and `agentops --version` work.
- `python -m pytest -v` passes.
