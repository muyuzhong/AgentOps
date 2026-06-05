"""把 append-only 的 eval-history.jsonl 读成结构化历史记录。

读取器只解析 eval 流程写出的 JSONL，绝不导入 git、绝不触网。它刻意容错：单条
损坏行，或 4.5 之前缺少 verdict_summary 的旧行，都不能让整次投影失败——坏行被
跳过，旧行的 verdict_summary 回退为空摘要 {}。读取有界：只保留最新的
MAX_HISTORY_RECORDS 条，并维持源顺序（即时间顺序）。缺失文件不在这里处理，交由
上层 runtime 转成结构化错误。
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path

# 显式有界限额：保持投影上下文可控，同时保留足够长的趋势窗口。
MAX_HISTORY_RECORDS = 1_000


@dataclass(frozen=True)
class HistoryRecord:
    """eval-history.jsonl 的一行经解析后的结构化记录。"""

    timestamp: str
    result: dict[str, object]  # 原样保留 EvalResult.to_dict()，投影按需取字段
    verdict_summary: dict[str, object]  # 缺失（4.5 前旧行）时回退为空摘要 {}


class EvalHistoryReader:
    """逐行读取 append-only 的 eval-history.jsonl，确定性、有界、容错。"""

    def read(self, history_path: Path) -> tuple[HistoryRecord, ...]:
        """逐行解析历史文件，返回有界且维持源顺序的记录元组。"""

        history_path = Path(history_path)
        # 只保留最新的 MAX_HISTORY_RECORDS 条；deque 自动丢弃更早的记录。
        records: deque[HistoryRecord] = deque(maxlen=MAX_HISTORY_RECORDS)

        # 使用 open + 迭代，避免一次性把整份历史读进内存；缺失文件由上层处理。
        with history_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                record = self._parse_line(raw_line)
                if record is not None:
                    records.append(record)

        return tuple(records)

    @staticmethod
    def _parse_line(raw_line: str) -> HistoryRecord | None:
        """把一行解析为 HistoryRecord；空行 / 坏行 / 缺可用 result 的行返回 None。"""

        line = raw_line.strip()
        if not line:
            return None
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None

        # result 是唯一必需键，且必须是字典才能供投影按字段取用。
        result = payload.get("result")
        if not isinstance(result, dict):
            return None

        # verdict_summary 缺失（旧行）或形态异常时一律回退为空摘要。
        verdict_summary = payload.get("verdict_summary", {})
        if not isinstance(verdict_summary, dict):
            verdict_summary = {}

        # timestamp 始终以字符串保留，缺失时回退为空串。
        timestamp = payload.get("timestamp", "")
        if not isinstance(timestamp, str):
            timestamp = str(timestamp)

        return HistoryRecord(
            timestamp=timestamp,
            result=result,
            verdict_summary=verdict_summary,
        )
