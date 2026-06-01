"""AgentOps Harness 命令行入口。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

from agentops import __version__
from agentops.initializers import SessionLogPolicy, run_init
from agentops.runtime.scan import ScanWorkflowError, run_scan


def resolve_session_log_policy(
    explicit_policy: SessionLogPolicy | None,
    *,
    stdin_isatty: bool,
    input_fn: Callable[[str], str] = input,
) -> SessionLogPolicy:
    """解析会话日志策略；非交互环境保守地保持本地私有。"""

    if explicit_policy is not None:
        return explicit_policy
    if not stdin_isatty:
        return SessionLogPolicy.PRIVATE

    prompt = (
        "Choose how AgentOps should manage .agentops/agentops-session.md:\n"
        "1. private - keep the session log local\n"
        "2. tracked - allow the repository to track the session log\n"
        "3. unmanaged - leave ignore behavior unchanged\n"
        "Selection [1-3]: "
    )
    policies = {
        "1": SessionLogPolicy.PRIVATE,
        "2": SessionLogPolicy.TRACKED,
        "3": SessionLogPolicy.UNMANAGED,
    }
    while True:
        answer = input_fn(prompt).strip()
        if answer in policies:
            return policies[answer]


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
    init_parser = subparsers.add_parser(
        "init",
        help="Install the AgentOps task-log protocol in a repository.",
    )
    init_parser.add_argument("--repo", required=True, type=Path)
    init_parser.add_argument(
        "--session-log-policy",
        choices=tuple(SessionLogPolicy),
        type=SessionLogPolicy,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """解析命令行参数并返回进程退出码。"""

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "scan":
        try:
            result = run_scan(args.repo, args.output)
        except ScanWorkflowError as error:
            failed_step = (
                error.trace.failures[0].step_name
                if error.trace.failures
                else "unknown"
            )
            print(f"AgentOps scan failed at step: {failed_step}", file=sys.stderr)
            if error.trace_artifact is not None:
                print(f"Wrote {error.trace_artifact.path}", file=sys.stderr)
            return 1
        print(f"AgentOps readiness score: {result.report.score}/100")
        for artifact in result.artifacts:
            print(f"Wrote {artifact.path}")
        return 0

    if args.command == "init":
        policy = resolve_session_log_policy(
            args.session_log_policy,
            stdin_isatty=sys.stdin.isatty(),
        )
        try:
            result = run_init(args.repo, policy)
        except ValueError as error:
            print(f"AgentOps initialization failed: {error}", file=sys.stderr)
            return 1
        for path in result.changed_paths:
            print(f"Wrote {path}")
        return 0

    parser.print_help()
    return 0
