"""将工作流 trace 写为便于排查问题的 JSON 产物。"""

from __future__ import annotations

import json
from pathlib import Path

from agentops.core.artifact import Artifact, ArtifactKind
from agentops.core.workflow import WorkflowTrace


class TraceWriter:
    """写出稳定、可读的工作流追踪文件。"""

    def write(self, trace: WorkflowTrace, output_dir: Path) -> Artifact:
        """创建输出目录并写出 UTF-8 JSON trace。"""

        output_dir.mkdir(parents=True, exist_ok=True)
        trace_path = output_dir / "agentops-trace.json"
        trace_path.write_text(
            json.dumps(
                trace.to_dict(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return Artifact(kind=ArtifactKind.WORKFLOW_TRACE, path=trace_path)
