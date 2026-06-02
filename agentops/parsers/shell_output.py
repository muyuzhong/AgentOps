"""把一次命令执行的输出规范化为有界的 ShellResult 证据。

解析器只整理已经采集到的 stdout/stderr 文本和退出码，不执行任何命令。
输出摘要保持有界；测试结果只在识别到受支持的 pytest 终端汇总时给出，
其余情况保留为 unknown（``test_result is None``），不做猜测。
"""

from __future__ import annotations

import re

from agentops.core.evidence import ShellResult, TestResult

# shell 摘要保留的最大字符数；超出后保留首尾并插入截断标记。
MAX_SHELL_SUMMARY_CHARS = 4_000
# 确定性截断标记；最终摘要长度不超过上限加上本标记长度。
TRUNCATION_MARKER = "\n...[truncated]...\n"

# 匹配 pytest 终端汇总行中的单个计数标记，如 "3 passed"、"2 failed"、"1 error"。
_PYTEST_COUNT_RE = re.compile(
    r"(\d+)\s+(passed|failed|skipped|errors|error|xfailed|xpassed|"
    r"warnings|warning|deselected)\b"
)
# 匹配 pytest 汇总行末尾的时长后缀，如 "in 0.12s"。
_PYTEST_DURATION_RE = re.compile(r"\bin\s+\d+(?:\.\d+)?s\b")


class ShellOutputParser:
    """规范化命令输出：有界摘要 + 保守的 pytest 结果识别。"""

    def parse(
        self,
        command: str,
        exit_code: int,
        stdout: str,
        stderr: str,
    ) -> ShellResult:
        """返回带有界摘要和可选测试结果的 ShellResult。"""

        # shell 是否成功只看退出码，不依赖输出内容。
        succeeded = exit_code == 0
        # 测试结果从完整未截断文本中识别，避免截断丢掉汇总行。
        test_result = self._recognize_pytest(stdout, stderr)
        summary, truncated = self._bounded_summary(stdout, stderr)
        return ShellResult(
            command=command,
            exit_code=exit_code,
            succeeded=succeeded,
            summary=summary,
            truncated=truncated,
            test_result=test_result,
        )

    @classmethod
    def _bounded_summary(cls, stdout: str, stderr: str) -> tuple[str, bool]:
        """构造有界摘要；两个流都有内容时分别加标签。"""

        if stdout and stderr:
            summary = f"[stdout]\n{stdout}\n[stderr]\n{stderr}"
        elif stdout:
            summary = stdout
        elif stderr:
            summary = stderr
        else:
            summary = ""

        if len(summary) <= MAX_SHELL_SUMMARY_CHARS:
            return summary, False

        # 保留首尾，使第一条诊断和最终汇总都可见。
        head_length = MAX_SHELL_SUMMARY_CHARS // 2
        tail_length = MAX_SHELL_SUMMARY_CHARS - head_length
        head = summary[:head_length]
        tail = summary[-tail_length:]
        return f"{head}{TRUNCATION_MARKER}{tail}", True

    @classmethod
    def _recognize_pytest(cls, stdout: str, stderr: str) -> TestResult | None:
        """识别受支持的 pytest 终端汇总；无法识别时返回 None。"""

        # pytest 汇总通常在 stdout，这里也兼顾 stderr。
        for stream in (stdout, stderr):
            if not stream:
                continue
            for raw_line in stream.splitlines():
                # 去掉两侧的 "=" 装饰和空白，得到纯汇总文本。
                line = raw_line.strip().strip("=").strip()
                # 受支持的汇总行都带 "in <时长>s" 后缀。
                if not _PYTEST_DURATION_RE.search(line):
                    continue
                counts = _PYTEST_COUNT_RE.findall(line)
                if not counts:
                    # 没有任何已知计数（如 "no tests ran"）不视为可识别汇总。
                    continue
                return cls._build_test_result(counts)
        return None

    @staticmethod
    def _build_test_result(counts: list[tuple[str, str]]) -> TestResult:
        """把计数标记累加为 TestResult；只统计关心的四类。"""

        tally = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
        for number, label in counts:
            value = int(number)
            if label == "passed":
                tally["passed"] += value
            elif label == "failed":
                tally["failed"] += value
            elif label == "skipped":
                tally["skipped"] += value
            elif label in ("error", "errors"):
                tally["errors"] += value
            # 其他类别（xfailed/xpassed/warnings/deselected）忽略，不影响成败判断。

        # 只要存在失败或错误就判定为未通过。
        succeeded = tally["failed"] == 0 and tally["errors"] == 0
        return TestResult(
            framework="pytest",
            passed=tally["passed"],
            failed=tally["failed"],
            skipped=tally["skipped"],
            errors=tally["errors"],
            succeeded=succeeded,
        )
