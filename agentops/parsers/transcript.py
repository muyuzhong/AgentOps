"""把有界的 `.agentops/agentops-session.md` 任务日志解析为 SessionTrace。

解析器只读取任务日志本身，逐行增量解析，绝不调用 ``Path.read_text()`` 把
整份日志载入内存，也绝不打开 Evidence References 指向的原始 transcript 文件。
所有限额都是显式常量，命中限额时在 ``truncated`` 上显式标记。
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

from agentops.core.session import SessionTrace, TaskReport, VerificationRecord

# 显式有界限额：保持 Phase 4 上下文可控，同时保留有用证据。
MAX_TASKS = 100
MAX_TASK_BYTES = 16_384
MAX_FIELD_CHARS = 2_000
MAX_LIST_ITEMS = 50

# 任务报告中的章节名。
_REQUIRED_SECTIONS = ("Goal", "Changes", "Verification")
_KNOWN_SECTIONS = (
    "Goal",
    "Context Used",
    "Changes",
    "Verification",
    "Issues",
    "Evidence References",
)
_TASK_HEADER_PREFIX = "## Task:"
_SECTION_HEADER_PREFIX = "### "


class TranscriptParseError(ValueError):
    """任务日志结构不合法时抛出，尽量在消息中指明任务和章节。"""


class TranscriptParser:
    """增量解析有界任务日志，返回规范化的 SessionTrace。"""

    def parse(self, source_path: Path) -> SessionTrace:
        """逐行读取任务日志，返回有界的 SessionTrace。"""

        source_path = Path(source_path)
        # 只保留最新的 MAX_TASKS 条；deque 自动丢弃更早的报告。
        tasks: deque[TaskReport] = deque(maxlen=MAX_TASKS)
        total_tasks = 0

        current_lines: list[str] | None = None
        current_bytes = 0

        # 使用 open + 迭代，避免一次性把整份日志读进内存。
        with source_path.open("r", encoding="utf-8", newline="") as handle:
            for raw_line in handle:
                line = raw_line.rstrip("\r\n")
                if line.strip().startswith(_TASK_HEADER_PREFIX):
                    # 遇到新任务头，先收尾上一个任务块。
                    if current_lines is not None:
                        tasks.append(self._build_task(current_lines))
                        total_tasks += 1
                    current_lines = [line]
                    current_bytes = len(raw_line.encode("utf-8"))
                    self._guard_task_size(current_bytes)
                elif current_lines is not None:
                    # 任务头之前的前言内容直接跳过。
                    current_bytes += len(raw_line.encode("utf-8"))
                    self._guard_task_size(current_bytes)
                    current_lines.append(line)

        if current_lines is not None:
            tasks.append(self._build_task(current_lines))
            total_tasks += 1

        # 丢弃过更早的任务则在会话层标记截断。
        session_truncated = total_tasks > MAX_TASKS
        return SessionTrace(
            source_path=source_path,
            tasks=tuple(tasks),
            truncated=session_truncated,
        )

    @staticmethod
    def _guard_task_size(current_bytes: int) -> None:
        """单个任务块超过字节上限时直接拒绝，而不是静默截断。"""

        if current_bytes > MAX_TASK_BYTES:
            raise TranscriptParseError("task report exceeds maximum size")

    def _build_task(self, lines: list[str]) -> TaskReport:
        """把一个任务块的行解析为校验过且有界的 TaskReport。"""

        title = lines[0].strip()[len(_TASK_HEADER_PREFIX):].strip()
        if not title:
            raise TranscriptParseError("task report is missing a title")

        sections = self._split_sections(lines[1:], title)
        for required in _REQUIRED_SECTIONS:
            if required not in sections:
                raise TranscriptParseError(
                    f"task '{title}' is missing required section: {required}"
                )

        truncated = False

        goal, goal_truncated = self._clip_text(self._join_text(sections["Goal"]))
        truncated = truncated or goal_truncated

        clipped_title, title_truncated = self._clip_text(title)
        truncated = truncated or title_truncated

        context_used, context_truncated = self._clip_list(
            self._list_items(sections.get("Context Used", []))
        )
        truncated = truncated or context_truncated

        changes, changes_truncated = self._clip_list(
            self._list_items(sections["Changes"])
        )
        truncated = truncated or changes_truncated

        issues, issues_truncated = self._clip_list(
            self._list_items(sections.get("Issues", []))
        )
        truncated = truncated or issues_truncated

        references, references_truncated = self._clip_list(
            self._list_items(sections.get("Evidence References", []))
        )
        truncated = truncated or references_truncated

        verification, verification_truncated = self._clip_list(
            self._parse_verification(sections["Verification"], title)
        )
        truncated = truncated or verification_truncated

        return TaskReport(
            title=clipped_title,
            goal=goal,
            context_used=context_used,
            changes=changes,
            verification=verification,
            issues=issues,
            evidence_references=references,
            truncated=truncated,
        )

    @classmethod
    def _split_sections(cls, body_lines: list[str], title: str) -> dict[str, list[str]]:
        """按 ``###`` 标题切分章节；拒绝重复的已知章节。"""

        sections: dict[str, list[str]] = {}
        current_section: str | None = None
        for line in body_lines:
            header = cls._section_header(line)
            if header is not None:
                if header in _KNOWN_SECTIONS:
                    if header in sections:
                        raise TranscriptParseError(
                            f"task '{title}' has a duplicate '{header}' section"
                        )
                    sections[header] = []
                    current_section = header
                else:
                    # 未知章节内容整体忽略，保持向前兼容。
                    current_section = None
            elif current_section is not None:
                sections[current_section].append(line)
        return sections

    @classmethod
    def _parse_verification(
        cls, lines: list[str], title: str
    ) -> list[VerificationRecord]:
        """解析 Command/Result 配对；落单的 Command 或 Result 视为非法。"""

        records: list[VerificationRecord] = []
        pending_command: str | None = None
        for line in lines:
            item = cls._bullet_content(line)
            if item is None:
                continue
            if item.startswith("Command:"):
                if pending_command is not None:
                    raise TranscriptParseError(
                        f"task '{title}' has a Command without a following Result"
                    )
                pending_command = cls._strip_backticks(item[len("Command:"):])
            elif item.startswith("Result:"):
                if pending_command is None:
                    raise TranscriptParseError(
                        f"task '{title}' has a Result without a preceding Command"
                    )
                result = cls._strip_backticks(item[len("Result:"):])
                records.append(
                    VerificationRecord(command=pending_command, result=result)
                )
                pending_command = None
            # 其他行（如说明文字）忽略。
        if pending_command is not None:
            raise TranscriptParseError(
                f"task '{title}' has a Command without a following Result"
            )
        return records

    @classmethod
    def _list_items(cls, lines: list[str]) -> list[str]:
        """提取章节中的列表项，去掉项目符号和包裹的反引号。"""

        items: list[str] = []
        for line in lines:
            content = cls._bullet_content(line)
            if content is None:
                continue
            normalized = cls._strip_backticks(content)
            if normalized:
                items.append(normalized)
        return items

    @staticmethod
    def _join_text(lines: list[str]) -> str:
        """把自由文本章节的非空行拼成单个字符串。"""

        return " ".join(stripped for line in lines if (stripped := line.strip()))

    @staticmethod
    def _clip_text(text: str) -> tuple[str, bool]:
        """超过字段字符上限时裁剪自由文本，并返回是否裁剪过。"""

        if len(text) > MAX_FIELD_CHARS:
            return text[:MAX_FIELD_CHARS], True
        return text, False

    @staticmethod
    def _clip_list(items: list) -> tuple[tuple, bool]:
        """超过列表上限时只保留前 MAX_LIST_ITEMS 项，并返回是否裁剪过。"""

        if len(items) > MAX_LIST_ITEMS:
            return tuple(items[:MAX_LIST_ITEMS]), True
        return tuple(items), False

    @staticmethod
    def _section_header(line: str) -> str | None:
        """识别 ``### 名称`` 章节标题，返回章节名或 None。"""

        stripped = line.strip()
        if stripped.startswith(_SECTION_HEADER_PREFIX):
            return stripped[len(_SECTION_HEADER_PREFIX):].strip()
        return None

    @staticmethod
    def _bullet_content(line: str) -> str | None:
        """返回列表项符号后的内容；非列表行返回 None。"""

        stripped = line.strip()
        for marker in ("- ", "* "):
            if stripped.startswith(marker):
                return stripped[len(marker):].strip()
        return None

    @staticmethod
    def _strip_backticks(text: str) -> str:
        """去掉首尾空白，并剥掉一层包裹的反引号。"""

        text = text.strip()
        if len(text) >= 2 and text.startswith("`") and text.endswith("`"):
            return text[1:-1]
        return text
