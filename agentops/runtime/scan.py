"""编排仓库扫描、readiness 评估和产物写出。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentops.core.artifact import Artifact
from agentops.core.evaluation import ReadinessReport
from agentops.evaluators.readiness import ReadinessEvaluator
from agentops.scanners.repo import RepoScanner
from agentops.writers.report import ReportWriter


@dataclass(frozen=True)
class ScanResult:
    """聚合一次仓库 readiness 扫描的结构化结果和产物。"""

    report: ReadinessReport
    artifacts: tuple[Artifact, ...]


def run_scan(repo_path: Path, output_dir: Path) -> ScanResult:
    """按照固定流水线执行仓库 readiness 扫描。"""

    # 编排层只维护步骤顺序，扫描、评估和写出细节分别留在独立模块。
    profile = RepoScanner().scan(repo_path)
    report = ReadinessEvaluator().evaluate(profile)
    artifacts = ReportWriter().write(report, output_dir)
    return ScanResult(report=report, artifacts=artifacts)
