"""使用固定规则收集仓库画像。"""

from __future__ import annotations

from pathlib import Path

from agentops.core.repo import RepoProfile

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
CI_FILES = (".gitlab-ci.yml", "azure-pipelines.yml")
TEST_COMMAND_RULES = (
    (("pyproject.toml", "requirements.txt"), "python -m pytest"),
    (("package.json",), "npm test"),
    (("Cargo.toml",), "cargo test"),
    (("go.mod",), "go test ./..."),
)


class RepoScanner:
    """只读扫描已知仓库入口，不递归解析源码。"""

    def scan(self, repo_path: Path) -> RepoProfile:
        """返回固定规则能够识别的仓库事实。"""

        if not repo_path.exists() or not repo_path.is_dir():
            raise ValueError("repository directory does not exist")

        constraint_files = self._existing_paths(repo_path, CONSTRAINT_FILES)
        test_directories = tuple(
            name for name in TEST_DIRECTORIES if (repo_path / name).is_dir()
        )
        project_markers = self._existing_paths(repo_path, PROJECT_MARKERS)

        return RepoProfile(
            root=repo_path,
            has_readme=any((repo_path / name).is_file() for name in README_FILES),
            constraint_files=constraint_files,
            test_directories=test_directories,
            ci_files=self._collect_ci_files(repo_path),
            project_markers=project_markers,
            test_commands=self._infer_test_commands(project_markers),
        )

    @staticmethod
    def _existing_paths(repo_path: Path, candidates: tuple[str, ...]) -> tuple[str, ...]:
        """按规则声明顺序返回存在的固定路径。"""

        return tuple(name for name in candidates if (repo_path / name).is_file())

    @staticmethod
    def _collect_ci_files(repo_path: Path) -> tuple[str, ...]:
        """枚举固定 CI 路径和 GitHub workflow 文件。"""

        ci_files = [
            name for name in CI_FILES if (repo_path / name).is_file()
        ]
        workflows_path = repo_path / ".github" / "workflows"
        if workflows_path.is_dir():
            for pattern in ("*.yml", "*.yaml"):
                ci_files.extend(
                    path.relative_to(repo_path).as_posix()
                    for path in workflows_path.glob(pattern)
                    if path.is_file()
                )
        return tuple(sorted(ci_files))

    @staticmethod
    def _infer_test_commands(project_markers: tuple[str, ...]) -> tuple[str, ...]:
        """仅根据项目标记保守推断常见测试命令。"""

        marker_set = set(project_markers)
        return tuple(
            command
            for markers, command in TEST_COMMAND_RULES
            if marker_set.intersection(markers)
        )
