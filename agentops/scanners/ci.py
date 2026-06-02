"""只读检测 CI 配置文件并保守提取验证命令。

本模块只读取已知路径的 CI 配置，使用 ``yaml.safe_load`` 解析受支持的字段，
不展开环境变量、不执行命令、不解释可复用 workflow、不跟随 include，
也不模拟任何 CI provider 的运行行为。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from agentops.core.evidence import CIProfile

# 仓库根目录下的固定 CI 配置文件名。
GITLAB_CI_FILE = ".gitlab-ci.yml"
AZURE_PIPELINES_FILE = "azure-pipelines.yml"

# GitHub Actions workflow 目录与受支持的文件后缀。
GITHUB_WORKFLOWS_DIR = (".github", "workflows")
GITHUB_WORKFLOW_SUFFIXES = (".yml", ".yaml")

# GitLab CI 中表示命令的脚本字段。
GITLAB_SCRIPT_KEYS = ("before_script", "script", "after_script")
# Azure Pipelines step 中表示命令的字段。
AZURE_STEP_KEYS = ("script", "bash", "powershell")


class CIScanError(RuntimeError):
    """CI 配置无法解析时抛出，消息中保留可定位的相对路径。"""


class CIDetector:
    """只读扫描已知 CI 配置文件，返回配置路径和去重后的验证命令。"""

    def scan(self, repo_path: Path) -> CIProfile:
        """检测 CI 配置文件，并提取保守的验证命令证据。"""

        if not repo_path.exists() or not repo_path.is_dir():
            raise ValueError("repository directory does not exist")

        # 收集 (相对路径, provider 标记)，便于后续按 provider 选择提取规则。
        detected = self._detect_config_files(repo_path)

        # 配置文件列表保持稳定的排序顺序，与既有 ci_files 行为一致。
        config_files = tuple(sorted(relative for relative, _ in detected))

        # 命令按配置文件排序顺序提取，全局去重并保留首次出现顺序。
        seen: set[str] = set()
        commands: list[str] = []
        extractors = {
            "github": self._extract_github_commands,
            "gitlab": self._extract_gitlab_commands,
            "azure": self._extract_azure_commands,
        }
        for relative, provider in sorted(detected):
            document = self._load_yaml(repo_path / relative, relative)
            if not isinstance(document, dict):
                # 空文件或非映射结构没有可提取的命令。
                continue
            for line in extractors[provider](document):
                if line not in seen:
                    seen.add(line)
                    commands.append(line)

        return CIProfile(
            config_files=config_files,
            validation_commands=tuple(commands),
        )

    @staticmethod
    def _detect_config_files(repo_path: Path) -> list[tuple[str, str]]:
        """枚举已知 CI 配置文件，返回 (相对路径, provider) 列表。"""

        detected: list[tuple[str, str]] = []
        for name, provider in (
            (GITLAB_CI_FILE, "gitlab"),
            (AZURE_PIPELINES_FILE, "azure"),
        ):
            if (repo_path / name).is_file():
                detected.append((name, provider))
        workflows_path = repo_path.joinpath(*GITHUB_WORKFLOWS_DIR)
        if workflows_path.is_dir():
            for path in workflows_path.iterdir():
                if path.is_file() and path.suffix in GITHUB_WORKFLOW_SUFFIXES:
                    relative = path.relative_to(repo_path).as_posix()
                    detected.append((relative, "github"))
        return detected

    @staticmethod
    def _load_yaml(path: Path, relative: str) -> object:
        """解析单个 CI YAML 文件；解析失败转为可定位的 CIScanError。"""

        try:
            text = path.read_text(encoding="utf-8")
            return yaml.safe_load(text)
        except (yaml.YAMLError, UnicodeDecodeError) as error:
            raise CIScanError(
                f"could not parse CI configuration file: {relative}"
            ) from error

    @classmethod
    def _extract_github_commands(cls, document: dict) -> list[str]:
        """提取 GitHub Actions ``jobs.*.steps[*].run`` 中的命令。"""

        lines: list[str] = []
        jobs = document.get("jobs")
        if isinstance(jobs, dict):
            for job in jobs.values():
                if isinstance(job, dict):
                    cls._collect_steps(job.get("steps"), ("run",), lines)
        return lines

    @classmethod
    def _extract_gitlab_commands(cls, document: dict) -> list[str]:
        """提取 GitLab 顶层与作业级 before_script/script/after_script。"""

        lines: list[str] = []
        # 顶层脚本字段。
        for key in GITLAB_SCRIPT_KEYS:
            cls._collect_command_value(document.get(key), lines)
        # 作业级脚本字段：任何包含脚本键的顶层映射都按作业处理。
        for value in document.values():
            if isinstance(value, dict):
                for key in GITLAB_SCRIPT_KEYS:
                    cls._collect_command_value(value.get(key), lines)
        return lines

    @classmethod
    def _extract_azure_commands(cls, document: dict) -> list[str]:
        """提取 Azure Pipelines ``steps[*]`` 与 ``jobs[*].steps[*]`` 的命令字段。"""

        lines: list[str] = []
        cls._collect_steps(document.get("steps"), AZURE_STEP_KEYS, lines)
        jobs = document.get("jobs")
        if isinstance(jobs, list):
            for job in jobs:
                if isinstance(job, dict):
                    cls._collect_steps(job.get("steps"), AZURE_STEP_KEYS, lines)
        return lines

    @classmethod
    def _collect_steps(
        cls, steps: object, keys: tuple[str, ...], lines: list[str]
    ) -> None:
        """从 steps 列表中按给定字段名提取命令。"""

        if not isinstance(steps, list):
            return
        for step in steps:
            if isinstance(step, dict):
                for key in keys:
                    cls._collect_command_value(step.get(key), lines)

    @staticmethod
    def _collect_command_value(value: object, lines: list[str]) -> None:
        """把字符串或字符串列表按非空行拆分、去除首尾空白后追加到 lines。"""

        if isinstance(value, str):
            raw_values = [value]
        elif isinstance(value, list):
            # 只接受字符串项，跳过 GitLab/Azure 中偶见的嵌套结构。
            raw_values = [item for item in value if isinstance(item, str)]
        else:
            return
        for raw in raw_values:
            for physical_line in raw.splitlines():
                stripped = physical_line.strip()
                if stripped:
                    lines.append(stripped)
