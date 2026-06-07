"""为反复出现的失败模式产出 Claude Code hook 提案（确定性投影）。

Phase 6 不发明新的运行时行为：check-session-log（Phase 3.5 起）、eval（Phase 4 起）都已
存在，本模块只是把“哪个失败模式该用哪个 hook、在什么事件上、跑什么现有命令来拦截”映射
出来，并渲染可直接粘贴的 settings.json 片段。复用 Phase 5 的复现阈值：只有达到阈值的失败
模式才值得提案；映射到同一 (event, command) 的多个模式合并为一条提案，证据合并、顺序确定。
"""

from __future__ import annotations

import json

from agentops.core.asset import HookProposal
from agentops.core.memory import FailureMode
from agentops.memory.candidates import RECURRENCE_THRESHOLD
from agentops.memory.failure_modes import CONFIRMED_DRIFT

# 失败模式 code → (hook 事件, 建议运行的现有 agentops 命令)。
_HOOK_FOR_CODE: dict[str, tuple[str, str]] = {
    "undeclared_change": ("Stop", "agentops eval --repo ."),
    "declared_not_changed": ("Stop", "agentops eval --repo ."),
    "cross_module_breadth": ("Stop", "agentops eval --repo ."),
    CONFIRMED_DRIFT: ("Stop", "agentops eval --repo ."),
}

# 每条提案保留的合并证据上限（结果有界）。
_MAX_EVIDENCE = 12


def derive_hook_proposals(
    modes: tuple[FailureMode, ...],
) -> tuple[HookProposal, ...]:
    """为达到复现阈值的失败模式产出 hook 提案；按 (event, command) 去重合并证据。"""

    # 按 (event, command) 聚合达到阈值、且有已知映射的失败模式。
    grouped: dict[tuple[str, str], list[FailureMode]] = {}
    for mode in modes:
        if mode.occurrence_count < RECURRENCE_THRESHOLD:
            continue
        target = _HOOK_FOR_CODE.get(mode.code)
        if target is None:
            continue
        grouped.setdefault(target, []).append(mode)

    proposals = [
        _proposal_for(event, command, group)
        for (event, command), group in grouped.items()
    ]
    # 确定性顺序：先按命令，再按首个失败 code。
    proposals.sort(key=lambda proposal: (proposal.command, proposal.failure_codes[0]))
    return tuple(proposals)


def _proposal_for(
    event: str,
    command: str,
    modes: list[FailureMode],
) -> HookProposal:
    """把映射到同一 (event, command) 的失败模式合并为一条 hook 提案。"""

    # 贡献 code 按字典序排序，保证 failure_codes / 证据 / rationale 顺序确定。
    sorted_modes = sorted(modes, key=lambda mode: mode.code)
    codes = tuple(mode.code for mode in sorted_modes)

    return HookProposal(
        slug=_slug(event, command),
        failure_codes=codes,
        event=event,
        title=_title(command),
        rationale=_rationale(event, command, sorted_modes),
        command=command,
        settings_snippet=_settings_snippet(event, command),
        evidence=_evidence(sorted_modes),
    )


def _command_token(command: str) -> str:
    """取命令里的 agentops 子命令（如 check-session-log / eval）作为 slug/标题词根。"""

    parts = command.split()
    # 形如 "agentops <subcommand> --repo ."；取第二个 token。
    return parts[1] if len(parts) >= 2 else command


def _slug(event: str, command: str) -> str:
    """稳定 id：<子命令>-<事件小写>-hook（同一 (event, command) 恒定）。"""

    return f"{_command_token(command)}-{event.lower()}-hook"


def _title(command: str) -> str:
    """确定性标题。"""

    return f"Add a `{_command_token(command)}` Stop hook"


def _rationale(event: str, command: str, modes: list[FailureMode]) -> str:
    """rationale：列出贡献 code 的 N/M 复现 + 该 hook 如何拦截（确定性模板）。"""

    recurrences = "; ".join(
        f"'{mode.code}' recurred in {mode.occurrence_count}/{mode.sample_count} evals"
        for mode in modes
    )
    return (
        f"{recurrences}. A {event} hook running `{command}` catches this at the end of "
        "the session before the work is handed off."
    )


def _settings_snippet(event: str, command: str) -> str:
    """渲染可直接粘贴的 Claude Code settings.json hooks 片段（两空格缩进、键序稳定）。"""

    fragment = {
        "hooks": {
            event: [
                {
                    "hooks": [
                        {"type": "command", "command": command},
                    ]
                }
            ]
        }
    }
    return json.dumps(fragment, ensure_ascii=False, indent=2)


def _evidence(modes: list[FailureMode]) -> tuple[str, ...]:
    """合并各贡献模式的 N/M 复现与热点路径证据（确定性、有界）。"""

    evidence: list[str] = []
    for mode in modes:
        evidence.append(
            f"{mode.code}: {mode.occurrence_count}/{mode.sample_count} evals "
            f"(last seen {mode.last_seen})"
        )
        if mode.hot_paths:
            evidence.append(f"{mode.code} hot paths: " + ", ".join(mode.hot_paths))
    return tuple(evidence[:_MAX_EVIDENCE])
