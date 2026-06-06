"""AgentOps Harness 命令行入口。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Callable

from agentops import __version__
from agentops.hooks import check_session_log
from agentops.initializers import SessionLogPolicy, run_init
from agentops.judges import IntentJudge, LLMIntentJudge
from agentops.llm import LLMClient, LLMError, OpenAICompatibleClient
from agentops.runtime.eval import EvalWorkflowError, run_eval
from agentops.runtime.memory import MemoryWorkflowError, run_memory
from agentops.runtime.scan import ScanWorkflowError, run_scan

# --intent-judge llm 默认指向的 OpenAI 兼容端点（mimo）；可用 --intent-base-url /
# AGENTOPS_LLM_BASE_URL 覆盖。仅是默认端点，不是写死的模型层级。
DEFAULT_LLM_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"


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
    check_parser = subparsers.add_parser(
        "check-session-log",
        help="Remind when no new task report was appended to the session log.",
    )
    check_parser.add_argument("--repo", required=True, type=Path)
    eval_parser = subparsers.add_parser(
        "eval",
        help="Evaluate the most recent task report against git truth.",
    )
    eval_parser.add_argument("--repo", required=True, type=Path)
    eval_parser.add_argument("--session", type=Path, default=None)
    eval_parser.add_argument("--diff-base", default="HEAD")
    eval_parser.add_argument("--output", type=Path, default=Path(".agentops"))
    eval_parser.add_argument(
        "--intent-judge",
        choices=("deterministic", "llm"),
        default="deterministic",
        help="Intent verdict source: deterministic (default, offline) or llm (opt-in).",
    )
    eval_parser.add_argument(
        "--intent-model",
        default=None,
        help="Model id for --intent-judge llm (e.g. mimo-v2.5-pro).",
    )
    eval_parser.add_argument(
        "--intent-base-url",
        default=None,
        help="OpenAI-compatible base URL for --intent-judge llm "
        "(default: $AGENTOPS_LLM_BASE_URL or the bundled mimo endpoint).",
    )
    memory_parser = subparsers.add_parser(
        "memory",
        help="Distill accumulated eval history into repository memory.",
    )
    memory_parser.add_argument("--repo", required=True, type=Path)
    memory_parser.add_argument("--history", type=Path, default=None)
    memory_parser.add_argument("--output", type=Path, default=Path(".agentops"))
    return parser


def _build_llm_client(args: argparse.Namespace) -> LLMClient:
    """构造 LLM 客户端；缺 key 抛 LLMError 交由调用方降级。

    单独抽成可打补丁的工厂：CLI 测试 monkeypatch 此函数注入 stub，绝不触网。
    base_url 与 api_key 走 CLI flag / 环境变量；model 由 --intent-model 提供。
    """

    base_url = (
        args.intent_base_url
        or os.environ.get("AGENTOPS_LLM_BASE_URL")
        or DEFAULT_LLM_BASE_URL
    )
    api_key = os.environ.get("AGENTOPS_LLM_API_KEY")
    if not api_key:
        raise LLMError("AGENTOPS_LLM_API_KEY is not set")
    return OpenAICompatibleClient(
        model=args.intent_model, base_url=base_url, api_key=api_key
    )


def _resolve_intent_judge(
    args: argparse.Namespace,
) -> tuple[IntentJudge | None, str | None]:
    """把 CLI 参数解析为（judge, 降级提示）。

    返回 ``None`` 表示走 run_eval 的确定性默认路径（与 Phase 4 完全一致）。请求
    ``llm`` 但缺 --intent-model 或客户端无法构造时，返回确定性默认并给出一行提示，
    让评测照常以退出码 0 完成。
    """

    if getattr(args, "intent_judge", "deterministic") != "llm":
        return None, None
    if not args.intent_model:
        return None, (
            "agentops: intent judge fell back to deterministic (no --intent-model)"
        )
    try:
        client = _build_llm_client(args)
    except LLMError as error:
        return None, (
            f"agentops: intent judge fell back to deterministic ({error})"
        )
    return LLMIntentJudge(client), None


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

    if args.command == "eval":
        # 未显式提供 --session 时回退到仓库内的默认任务日志。
        session_path = (
            args.session
            if args.session is not None
            else args.repo / ".agentops" / "agentops-session.md"
        )
        # 解析意图判官：默认确定性；--intent-judge llm 不可用时降级并给出一行提示。
        intent_judge, fallback_notice = _resolve_intent_judge(args)
        if fallback_notice is not None:
            print(fallback_notice, file=sys.stderr)
        try:
            run = run_eval(
                args.repo,
                session_path,
                args.output,
                diff_base=args.diff_base,
                intent_judge=intent_judge,
            )
        except EvalWorkflowError as error:
            failed_step = (
                error.trace.failures[0].step_name
                if error.trace.failures
                else "unknown"
            )
            print(f"AgentOps eval failed at step: {failed_step}", file=sys.stderr)
            if error.trace_artifact is not None:
                print(f"Wrote {error.trace_artifact.path}", file=sys.stderr)
            return 1
        print(f"AgentOps scope-discipline score: {run.result.score}/100")
        for artifact in run.artifacts:
            print(f"Wrote {artifact.path}")
        return 0

    if args.command == "memory":
        # 未显式提供 --history 时回退到仓库内默认的累积历史。
        history_path = (
            args.history
            if args.history is not None
            else args.repo / ".agentops" / "eval-history.jsonl"
        )
        try:
            run = run_memory(args.repo, history_path, args.output)
        except MemoryWorkflowError as error:
            # 缺失/空历史等结构化失败：打印保留下来的失败原因（含"先跑 agentops eval"
            # 的指引），不暴露 traceback；意外异常不被隐藏。
            message = (
                error.trace.failures[0].message
                if error.trace.failures
                else "unknown error"
            )
            print(f"AgentOps memory failed: {message}", file=sys.stderr)
            if error.trace_artifact is not None:
                print(f"Wrote {error.trace_artifact.path}", file=sys.stderr)
            return 1
        memory = run.memory
        print(
            f"AgentOps repository memory: {memory.sample_count} eval(s), "
            f"trend {memory.trend.direction}; "
            f"{len(memory.failure_modes)} failure mode(s), "
            f"{len(memory.rule_candidates)} rule candidate(s), "
            f"{len(memory.skill_candidates)} skill candidate(s)"
        )
        for artifact in run.artifacts:
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

    if args.command == "check-session-log":
        try:
            result = check_session_log(args.repo)
        except ValueError as error:
            print(f"AgentOps check failed: {error}", file=sys.stderr)
            return 1
        if result.has_new_content:
            return 0
        # 没有新追加时把提醒写到 stderr，并以非零退出码提示调用方（如 Stop hook）。
        print(result.reminder, file=sys.stderr)
        return 1

    parser.print_help()
    return 0
