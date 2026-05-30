# Phase 1 Minimal Repo Scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the first useful vertical slice: `agentops scan --repo <repo-path>` produces a deterministic AI coding readiness report in Markdown and JSON.

**Architecture:** Phase 1 adds a read-only repository scanner, a deterministic readiness evaluator, artifact writers, and a small orchestration function. The CLI remains a thin adapter. Scanning is intentionally conservative: it recognizes a fixed set of files and directories, explains every score deduction, and never modifies the target repository.

**Tech Stack:** Python 3.11+, standard library `argparse`, `json`, `pathlib`, `pytest`

---

## Prerequisite

Complete `docs/superpowers/plans/2026-05-30-phase-0-core-scaffold.md` first.

## Scope Guard

The first scan detects only:

- README presence.
- `AGENTS.md` and `CLAUDE.md` presence.
- Common test directories.
- Common CI files.
- Common project markers.
- Likely test commands inferred from project markers.

Do not add:

- Recursive source-code parsing.
- LLM-based recommendations.
- Git history analysis.
- Session transcript parsing.
- Automatic edits to the scanned repository.
- Plugin registries.

## Target File Structure

```text
agentops/
  cli.py
  core/
    evaluation.py
    repo.py
  evaluators/
    __init__.py
    readiness.py
  runtime/
    __init__.py
    scan.py
  scanners/
    __init__.py
    repo.py
  writers/
    __init__.py
    report.py
tests/
  test_cli.py
  test_readiness_evaluator.py
  test_repo_scanner.py
  test_report_writer.py
  test_scan_runtime.py
```

## Task 1: Extend `RepoProfile` for scan output

**Files:**
- Modify: `agentops/core/repo.py`
- Modify: `tests/test_core_models.py`

- [ ] **Step 1: Add failing tests**

Require `RepoProfile` to carry inferred test commands:

```python
def test_repo_profile_serializes_test_commands() -> None:
    profile = RepoProfile(
        root=Path("demo"),
        test_commands=("python -m pytest",),
    )

    assert profile.to_dict()["test_commands"] == ["python -m pytest"]
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_core_models.py -v
```

Expected: FAIL because `test_commands` is not defined.

- [ ] **Step 3: Add the field**

Add:

```python
test_commands: tuple[str, ...] = ()
```

Include it in `to_dict()`.

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_core_models.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add agentops/core/repo.py tests/test_core_models.py
git commit -m "feat: record inferred repository test commands"
```

## Task 2: Implement the read-only repository scanner

**Files:**
- Create: `agentops/scanners/__init__.py`
- Create: `agentops/scanners/repo.py`
- Create: `tests/test_repo_scanner.py`

- [ ] **Step 1: Write failing scanner tests**

Cover a repository with:

- `README.md`
- `AGENTS.md`
- `tests/`
- `.github/workflows/ci.yml`
- `pyproject.toml`

Require:

```python
profile = RepoScanner().scan(repo_path)

assert profile.has_readme is True
assert profile.constraint_files == ("AGENTS.md",)
assert profile.test_directories == ("tests",)
assert profile.ci_files == (".github/workflows/ci.yml",)
assert profile.project_markers == ("pyproject.toml",)
assert profile.test_commands == ("python -m pytest",)
```

Also add:

```python
def test_repo_scanner_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="repository directory does not exist"):
        RepoScanner().scan(tmp_path / "missing")
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_repo_scanner.py -v
```

Expected: FAIL because `RepoScanner` does not exist.

- [ ] **Step 3: Implement fixed scan rules**

Implement `RepoScanner` with constants:

```python
README_FILES = ("README.md", "README.rst", "README.txt", "README")
CONSTRAINT_FILES = ("AGENTS.md", "CLAUDE.md")
TEST_DIRECTORIES = ("tests", "test", "__tests__", "spec")
PROJECT_MARKERS = (
    "pyproject.toml",
    "requirements.txt",
    "package.json",
    "Cargo.toml",
    "go.mod",
)
```

Detect CI files under:

```text
.github/workflows/*.yml
.github/workflows/*.yaml
.gitlab-ci.yml
azure-pipelines.yml
```

Infer commands conservatively:

| Marker | Test command |
| --- | --- |
| `pyproject.toml` or `requirements.txt` | `python -m pytest` |
| `package.json` | `npm test` |
| `Cargo.toml` | `cargo test` |
| `go.mod` | `go test ./...` |

Use sorted relative paths so output is deterministic.

- [ ] **Step 4: Keep scanner read-only**

The scanner may call only `Path.exists()`, `Path.is_dir()`, and bounded file listing for known CI locations. It must not write files, execute commands, or recursively inspect source code.

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/test_repo_scanner.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add agentops/scanners tests/test_repo_scanner.py
git commit -m "feat: add read-only repository scanner"
```

## Task 3: Implement deterministic readiness evaluation

**Files:**
- Create: `agentops/evaluators/__init__.py`
- Create: `agentops/evaluators/readiness.py`
- Create: `tests/test_readiness_evaluator.py`

- [ ] **Step 1: Write failing evaluation tests**

Require a perfect starter profile to score `100`:

```python
def test_evaluator_scores_complete_profile_as_ready() -> None:
    profile = RepoProfile(
        root=Path("demo"),
        has_readme=True,
        constraint_files=("AGENTS.md",),
        test_directories=("tests",),
        ci_files=(".github/workflows/ci.yml",),
        project_markers=("pyproject.toml",),
        test_commands=("python -m pytest",),
    )

    report = ReadinessEvaluator().evaluate(profile)

    assert report.score == 100
    assert report.findings == ()
```

Require deductions for missing files:

```python
def test_evaluator_explains_missing_agent_instructions() -> None:
    profile = RepoProfile(root=Path("demo"), has_readme=True)

    report = ReadinessEvaluator().evaluate(profile)

    assert report.score < 100
    assert any(item.code == "missing_agent_instructions" for item in report.findings)
    assert any(
        item.kind is RecommendationKind.ADD_CONSTRAINT_FILE
        for item in report.recommendations
    )
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_readiness_evaluator.py -v
```

Expected: FAIL because `ReadinessEvaluator` does not exist.

- [ ] **Step 3: Implement explicit scoring rules**

Use a `100` point baseline with transparent deductions:

| Missing capability | Deduction |
| --- | ---: |
| README | 15 |
| `AGENTS.md` and `CLAUDE.md` both absent | 25 |
| Common test directory absent | 25 |
| CI config absent | 15 |
| Project marker absent | 10 |
| Inferred test command absent | 10 |

Every deduction must generate:

- One `Finding`.
- A stable machine-readable `code`.
- One actionable `Recommendation`.

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_readiness_evaluator.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add agentops/evaluators tests/test_readiness_evaluator.py
git commit -m "feat: evaluate repository agent readiness"
```

## Task 4: Write Markdown and JSON artifacts

**Files:**
- Create: `agentops/writers/__init__.py`
- Create: `agentops/writers/report.py`
- Create: `tests/test_report_writer.py`

- [ ] **Step 1: Write failing writer tests**

Require:

```python
artifacts = ReportWriter().write(report, output_dir)

assert (output_dir / "agentops-report.md").exists()
assert (output_dir / "agentops-score.json").exists()
assert [item.kind.value for item in artifacts] == [
    "markdown_report",
    "json_score",
]
```

Assert Markdown contains:

```text
# AgentOps Repository Readiness Report
Score: 100/100
```

Assert JSON contains:

```python
json.loads((output_dir / "agentops-score.json").read_text(encoding="utf-8"))["score"] == 100
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_report_writer.py -v
```

Expected: FAIL because `ReportWriter` does not exist.

- [ ] **Step 3: Implement writer**

Implement:

```python
class ReportWriter:
    def write(self, report: ReadinessReport, output_dir: Path) -> tuple[Artifact, ...]:
        ...
```

Behavior:

- Create `output_dir` when missing.
- Write UTF-8 Markdown.
- Write stable UTF-8 JSON with `ensure_ascii=False` and `indent=2`.
- Include score, detected repository facts, findings, and recommendations.
- Return artifacts in Markdown-then-JSON order.

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_report_writer.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add agentops/writers tests/test_report_writer.py
git commit -m "feat: write repository readiness artifacts"
```

## Task 5: Add the scan workflow runtime

**Files:**
- Create: `agentops/runtime/__init__.py`
- Create: `agentops/runtime/scan.py`
- Create: `tests/test_scan_runtime.py`

- [ ] **Step 1: Write a failing workflow test**

Require:

```python
result = run_scan(repo_path, output_dir)

assert result.report.profile.root == repo_path
assert result.report.score == 100
assert {item.path.name for item in result.artifacts} == {
    "agentops-report.md",
    "agentops-score.json",
}
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
python -m pytest tests/test_scan_runtime.py -v
```

Expected: FAIL because runtime does not exist.

- [ ] **Step 3: Implement orchestration**

Define:

```python
@dataclass(frozen=True)
class ScanResult:
    report: ReadinessReport
    artifacts: tuple[Artifact, ...]


def run_scan(repo_path: Path, output_dir: Path) -> ScanResult:
    profile = RepoScanner().scan(repo_path)
    report = ReadinessEvaluator().evaluate(profile)
    artifacts = ReportWriter().write(report, output_dir)
    return ScanResult(report=report, artifacts=artifacts)
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_scan_runtime.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add agentops/runtime tests/test_scan_runtime.py
git commit -m "feat: orchestrate repository readiness scan"
```

## Task 6: Expose `agentops scan`

**Files:**
- Modify: `agentops/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add failing CLI tests**

Require:

```python
def test_scan_command_writes_artifacts(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "README.md").write_text("# Demo", encoding="utf-8")
    output_dir = tmp_path / "output"

    exit_code = main([
        "scan",
        "--repo",
        str(repo_path),
        "--output",
        str(output_dir),
    ])

    assert exit_code == 0
    assert (output_dir / "agentops-report.md").exists()
    assert (output_dir / "agentops-score.json").exists()
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_cli.py -v
```

Expected: FAIL because `scan` is not registered.

- [ ] **Step 3: Register subcommand**

Update `build_parser()`:

```python
subparsers = parser.add_subparsers(dest="command")
scan_parser = subparsers.add_parser(
    "scan",
    help="Scan a repository for AI coding readiness.",
)
scan_parser.add_argument("--repo", required=True, type=Path)
scan_parser.add_argument("--output", type=Path, default=Path(".agentops"))
```

Update `main()`:

```python
if args.command == "scan":
    result = run_scan(args.repo, args.output)
    print(f"AgentOps readiness score: {result.report.score}/100")
    for artifact in result.artifacts:
        print(f"Wrote {artifact.path}")
    return 0
```

When no subcommand is supplied, print help and return `0`.

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add agentops/cli.py tests/test_cli.py
git commit -m "feat: expose repository scan command"
```

## Task 7: Verify Phase 1 against a real repository

- [ ] **Step 1: Run all automated tests**

Run:

```powershell
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Scan AgentOps Harness itself**

Run:

```powershell
agentops scan --repo "D:\harness agent\agentops_harness" --output ".agentops\self-scan"
```

Expected:

- command exits with code `0`;
- `.agentops/self-scan/agentops-report.md` exists;
- `.agentops/self-scan/agentops-score.json` exists;
- report explains deductions rather than only printing a score.

- [ ] **Step 3: Inspect JSON**

Run:

```powershell
Get-Content -LiteralPath '.agentops\self-scan\agentops-score.json' -Encoding utf8
```

Expected: valid JSON with `profile`, `score`, `findings`, and `recommendations`.

- [ ] **Step 4: Confirm generated artifacts are ignored**

Run:

```powershell
git status --short
```

Expected: no `.agentops/` files appear.

- [ ] **Step 5: Commit any final documentation correction if needed**

Only update documentation if actual command behavior differs from `README.md`.

## Exit Criteria

Phase 1 is complete when:

- `agentops scan --repo <repo-path>` works on a real local repository.
- The scanner performs no writes inside the scanned repository.
- Markdown and JSON artifacts are generated under the selected output directory.
- Every score deduction has a visible finding and actionable recommendation.
- Results are deterministic for an unchanged repository.
- `python -m pytest -v` passes.

