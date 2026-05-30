"""AgentOps Harness 命令行入口。"""

from __future__ import annotations

import argparse

from agentops import __version__


def build_parser() -> argparse.ArgumentParser:
    """构建 Phase 0 的最小命令行解析器。"""

    parser = argparse.ArgumentParser(
        prog="agentops",
        description="Evaluate and improve AI coding work in real repositories.",
    )
    # Phase 0 仅建立 CLI 接入骨架；仓库扫描子命令将在 Phase 1 增加。
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv: list[str] | None = None) -> int:
    """解析命令行参数并返回进程退出码。"""

    parser = build_parser()
    parser.parse_args(argv)
    return 0
