# AgentOps Harness 项目记忆

本文档保存跨会话开发事实。每个 AI coding agent 开始任务前必须阅读本文档；合并任何功能后必须更新本文档。

## 更新协议

开始任务前：

1. 阅读 `agent.md`。
2. 阅读本文档。
3. 阅读与当前任务相关的设计文档和实施计划。
4. 运行 `git status --short`，确认是否存在其他人留下的修改。
5. 运行 `python -m pytest -v`，确认基线状态。

完成任务后：

1. 运行相关测试和完整测试。
2. 更新“当前状态”“最近完成”和“下一步”。
3. 如果设计决策发生变化，更新“关键决策”。
4. 如果发现未解决问题，写入“已知限制和风险”。
5. 在合并到 `main` 后提交本文档更新。

并行 worktree 不直接修改本文档。由集成者在功能合并到 `main` 后统一更新。

## 当前状态

- 当前分支：`main`
- 当前阶段：Phase 2 执行中，Task 1-3 已完成，下一步执行 Task 4。
- 当前版本：`0.1.0`
- 当前可用命令：
  - `agentops --help`
  - `agentops --version`
  - `agentops scan --repo <repo-path>`
  - `agentops scan --repo <repo-path> --output <output-path>`
- 当前完整测试命令：

```powershell
python -m pytest -v
```

- 最近一次确认的测试结果：2026-05-31 执行 `python -m pytest -v`，共 `44 passed`。

## 已完成能力

### Phase 0：Core Scaffold

- 已初始化 Python 包和 CLI 入口。
- 已配置 `pyproject.toml` 和 editable install。
- 已实现核心领域模型：
  - `RepoProfile`
  - `Recommendation`
  - `RecommendationKind`
  - `Finding`
  - `Severity`
  - `ReadinessReport`
  - `Artifact`
  - `ArtifactKind`
- 已实现稳定的 JSON 友好序列化。
- 已限制 readiness score 必须为 `0` 到 `100` 的严格整数，排除 `bool`。
- 已增加 Phase 0 CLI 和核心模型测试。

### Phase 1：Repo Scan

- 已为 `RepoProfile` 增加 `test_commands` 字段及稳定序列化。
- 已实现只读 `RepoScanner`：
  - 识别 README、Agent 约束文件、测试目录、CI 文件和项目标记。
  - 根据项目标记保守推断常见测试命令。
  - 使用固定规则和排序后的相对路径，保证扫描结果稳定。
- 已实现确定性 `ReadinessEvaluator`：
  - 使用 `100` 分基线和六条显式扣分规则。
  - 每条扣分都生成稳定 code、证据和可执行建议。
- 已实现 `ReportWriter`：
  - 写出 UTF-8 Markdown readiness 报告。
  - 写出稳定 JSON 评分、证据和建议。
- 已实现 scan runtime，按照 scanner、evaluator、writer 的固定顺序执行。
- 已暴露 `agentops scan --repo <repo-path>` CLI 子命令，并支持 `--output`。
- 已对 AgentOps Harness 仓库执行真实自扫描：
  - 当前评分为 `60/100`。
  - 缺失 Agent 约束文件扣除 `25` 分。
  - 缺失常见 CI 配置扣除 `15` 分。

### Phase 2：Workflow Runtime（Task 1-3）

- 已实现 workflow 状态、事件和 trace 模型：
  - `WorkflowStatus`
  - `WorkflowEventType`
  - `StepFailure`
  - `WorkflowEvent`
  - `WorkflowTrace`
- 已在 `WorkflowEvent` 边界拒绝无时区时间，并把带时区时间统一归一化为 UTC。
- 已实现同步确定性 `WorkflowRunner`：
  - 按声明顺序执行步骤。
  - required step 失败时停止后续步骤并保留失败 trace。
  - optional step 失败时记录 recoverable failure，并以 `completed_with_warnings` 完成。
- 已实现 `TraceWriter`，可以写出 UTF-8、稳定排序、两空格缩进并带尾随换行的 `agentops-trace.json`。
- 当前 `run_scan()` 尚未接入新 runtime；`agentops scan` 还不会自动写出 trace。

## 当前文件边界

| 路径 | 职责 |
| --- | --- |
| `agentops/cli.py` | CLI 入口和 `scan` 子命令薄适配器 |
| `agentops/core/repo.py` | 仓库画像模型 |
| `agentops/core/evaluation.py` | Finding 和 ReadinessReport |
| `agentops/core/recommendation.py` | 建议类型和建议模型 |
| `agentops/core/artifact.py` | 输出产物模型 |
| `agentops/core/workflow.py` | workflow 状态、事件、失败和 trace 模型 |
| `agentops/scanners/repo.py` | 只读仓库扫描与测试命令推断 |
| `agentops/evaluators/readiness.py` | 确定性 readiness 扣分规则 |
| `agentops/writers/report.py` | Markdown 和 JSON readiness 产物写出 |
| `agentops/writers/trace.py` | JSON workflow trace 产物写出 |
| `agentops/runtime/scan.py` | scan 固定流水线编排 |
| `agentops/runtime/workflow.py` | 同步确定性 workflow runner |
| `tests/test_cli.py` | CLI 行为测试 |
| `tests/test_core_models.py` | 核心模型测试 |
| `tests/test_repo_scanner.py` | 仓库扫描器测试 |
| `tests/test_readiness_evaluator.py` | readiness 评分规则测试 |
| `tests/test_report_writer.py` | readiness 产物写出测试 |
| `tests/test_scan_runtime.py` | scan 流水线集成测试 |

## 下一步

执行：

```text
docs/superpowers/plans/2026-05-31-phase-2-workflow-runtime.md
```

Phase 2 的 Task 1-3 已完成。下一步执行 Task 4：把 `run_scan()` 接入 `WorkflowRunner`，让成功和失败扫描都保留 trace 证据。

## 关键决策

- 项目定位为 AI coding 工作质量评测与优化 Harness。
- 不实现另一个 coding agent。
- 第一阶段使用确定性 workflow。
- 后续增加监督型 Agent Loop，但它不直接写代码。
- 先做只读仓库扫描和离线评估，再做自动修改或实时干预。
- 先使用确定性规则，再引入 LLM 辅助诊断和建议。
- 每次评分扣分都必须附带证据和可执行建议。
- 并行开发使用 `.worktrees/`，分支命名为 `codex/<scope>`。
- 集中记忆只在集成分支更新。
- workflow event 时间戳必须带时区，并在模型边界统一归一化为 UTC。
- workflow required step 失败时停止；optional step 失败时降级继续执行。

## 已知限制和风险

- 当前没有 session parser、memory store 或 watcher。
- 通用 workflow 模型、runner 和 trace writer 已实现，但 `runtime/scan.py` 尚未接入它们；CLI 暂时不会自动写出 `agentops-trace.json`。
- `ReadinessEvaluator` 当前信任内部 `RepoProfile` 已由 scanner 规范化；未来开放 SDK 前需要补充输入契约校验。
- README 中列出的扫描和评测能力仍属于开发中能力。
- 项目尚未确定正式 License。

## 最近完成

| 日期 | 提交 | 内容 |
| --- | --- | --- |
| 2026-05-31 | `2d4d783` | 收紧 workflow event UTC 时间边界，并补充序列化与 writer 格式回归测试 |
| 2026-05-31 | `06eb6b6` | 写出 JSON workflow trace 产物 |
| 2026-05-31 | `79e1557` | 实现 required/optional step 语义的确定性 workflow runner |
| 2026-05-31 | `7ac79ba` | 定义 workflow 状态、事件、失败和 trace 模型 |
| 2026-05-31 | `cd785a9` | 收紧 scanner 文件型事实识别，并补充只读和稳定性回归测试 |
| 2026-05-31 | `deffed1` | 暴露 `agentops scan` CLI 子命令和输出目录参数 |
| 2026-05-31 | `5f18633` | 串联 scanner、evaluator 和 writer 的 scan runtime |
| 2026-05-31 | `521a37c` | 写出 Markdown 和 JSON readiness 产物 |
| 2026-05-30 | `17d44ce` | 实现确定性 readiness 评分规则、证据和改进建议 |
| 2026-05-30 | `a4f350f` | 实现固定规则、只读且稳定排序的仓库扫描器 |
| 2026-05-30 | `11a1b84` | 为仓库画像增加推断测试命令字段 |
| 2026-05-30 | `f350902` | 严格校验 readiness score 类型，并补充 CLI 边界测试 |
| 2026-05-30 | `b5645d5` | 收敛 GitHub README，只保留面向用户的内容 |
| 2026-05-30 | `36ba9d1` | 完善 `.gitignore`，补充 README 初版产品说明 |
