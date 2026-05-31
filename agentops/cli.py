"""AgentOps Harness 命令行入口。"""

from __future__ import annotations

import argparse
from pathlib import Path

from agentops import __version__
from agentops.runtime.scan import run_scan


def build_parser() -> argparse.ArgumentParser:
    """构建 AgentOps 命令行解析器。"""

    parser = argparse.ArgumentParser(
        prog="agentops",
        description="Evaluate and improve AI coding work in real repositories.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")
    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan a repository for AI coding readiness.",
    )
    scan_parser.add_argument("--repo", required=True, type=Path)
    scan_parser.add_argument("--output", type=Path, default=Path(".agentops"))
    return parser


def main(argv: list[str] | None = None) -> int:
    """解析命令行参数并返回进程退出码。"""

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "scan":
        result = run_scan(args.repo, args.output)
        print(f"AgentOps readiness score: {result.report.score}/100")
        for artifact in result.artifacts:
            print(f"Wrote {artifact.path}")
        return 0

    parser.print_help()
    return 0
