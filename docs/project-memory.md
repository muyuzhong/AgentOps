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
- 当前阶段：Phase 3 analysis tools 正在执行，Task 1 公共 evidence models、Task 2 有界 session models 和 Task 3 repository initializer 已完成。
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

- 最近一次确认的测试结果：2026-05-31 执行 `python -m pytest -v`，共 `103 passed`。

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

### Phase 2：Workflow Runtime

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
- 已将 `run_scan()` 接入 `WorkflowRunner`：
  - 顺序执行 `scan_repository`、`evaluate_readiness` 和 `write_readiness_artifacts`。
  - 成功扫描写出 readiness 报告、JSON 评分和 workflow trace。
  - required step 失败时保留失败 trace；trace 文件不可写时仍保留原始 workflow failure。
- 已为 CLI 增加结构化失败处理：
  - `ScanWorkflowError` 返回退出码 `1`。
  - stderr 输出失败步骤，并在 trace 可写时输出 trace 路径。
  - 非 `ScanWorkflowError` 不会被 CLI 隐藏。

### Phase 3：Analysis Tools

- 已完成 Task 1 公共 evidence models：
  - `ChangeKind`
  - `ChangedFile`
  - `DiffSummary`
  - `GitStatus`
  - `CIProfile`
  - `TestResult`
  - `ShellResult`
- 所有 evidence models 均为不可变 dataclass，并提供稳定、JSON 友好的 `to_dict()`。
- diff 与 test 计数只允许非负严格整数；`TestResult` 的可选计数允许使用 `None` 表达 unknown。
- 已完成 Task 2 有界 session models：
  - `VerificationRecord`
  - `TaskReport`
  - `SessionTrace`
- session models 均为不可变 dataclass，并在 `to_dict()` 边界将 `Path` 转为字符串、tuple 转为 list。
- `TaskReport.truncated` 和 `SessionTrace.truncated` 显式记录后续 parser 是否裁剪过证据。
- 已完成 Task 3 repository initializer：
  - `SessionLogPolicy`
  - `InitResult`
  - `run_init()`
- initializer 通过显式 API 写入或刷新 `.agentops/session-protocol.md`，仅在缺失时创建 `.agentops/agentops-session.md`。
- 已支持 `private`、`tracked` 和 `unmanaged` 三种 session log 策略；只管理 `.agentops/.gitignore` 中的 AgentOps 托管块，不修改根 `.gitignore`。
- 已按独立 marker 行识别托管块，保留块外用户内容和原始 CRLF/LF 风格；写入前完成路径与 marker 校验。
- 文本写入使用同目录 staging 和 replace；staging 或 replace 失败时清理临时文件，并回滚已替换内容。
- 尚未实现 Phase 3 后续 CLI、parser、analyzer 和 CI detector。

## 当前文件边界

| 路径 | 职责 |
| --- | --- |
| `agentops/cli.py` | CLI 入口和 `scan` 子命令薄适配器 |
| `agentops/core/repo.py` | 仓库画像模型 |
| `agentops/core/evaluation.py` | Finding 和 ReadinessReport |
| `agentops/core/recommendation.py` | 建议类型和建议模型 |
| `agentops/core/artifact.py` | 输出产物模型 |
| `agentops/core/evidence.py` | diff、git、CI、shell 和 test 公共证据模型 |
| `agentops/core/session.py` | 有界任务日志的 session 证据模型 |
| `agentops/core/workflow.py` | workflow 状态、事件、失败和 trace 模型 |
| `agentops/initializers/repo.py` | 显式安装 session protocol、托管指令块和 session log 策略 |
| `agentops/scanners/repo.py` | 只读仓库扫描与测试命令推断 |
| `agentops/evaluators/readiness.py` | 确定性 readiness 扣分规则 |
| `agentops/writers/report.py` | Markdown 和 JSON readiness 产物写出 |
| `agentops/writers/trace.py` | JSON workflow trace 产物写出 |
| `agentops/runtime/scan.py` | scan workflow 编排、trace 写出和结构化失败 |
| `agentops/runtime/workflow.py` | 同步确定性 workflow runner |
| `tests/test_cli.py` | CLI 行为测试 |
| `tests/test_core_models.py` | 核心模型测试 |
| `tests/test_evidence_models.py` | Phase 3 公共 evidence models 测试 |
| `tests/test_session_models.py` | Phase 3 有界 session models 测试 |
| `tests/test_repo_initializer.py` | Phase 3 repository initializer 测试 |
| `tests/test_repo_scanner.py` | 仓库扫描器测试 |
| `tests/test_readiness_evaluator.py` | readiness 评分规则测试 |
| `tests/test_report_writer.py` | readiness 产物写出测试 |
| `tests/test_scan_runtime.py` | scan 流水线集成测试 |

## 下一步

Phase 3 Task 3 已完成。下一步继续执行 Phase 3 analysis tools 实施计划中的 Task 4：

```text
docs/superpowers/plans/2026-05-31-phase-3-analysis-tools.md
```

Task 4 将把 `agentops init --repo <repo-path>` 接入 CLI，解析交互或显式 session log policy，并保持现有 scan 行为不变。Phase 3 仍只负责确定性采集和规范化，不提前实现 `agentops eval`、质量评分或 LLM 摘要。

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
- Phase 3 不默认读取完整聊天记录。coding agent 每完成一个独立任务后，向 `.agentops/agentops-session.md` 追加简短汇报；parser 只保留有界结构化证据和原文引用。
- `agentops init` 是显式写操作。已有 `CLAUDE.md` 或 `AGENTS.md` 时追加托管协议块；两者同时存在时都更新；两者都不存在时创建或更新 `rule.md`。
- `agentops init` 允许用户选择 session log 为 `private`、`tracked` 或 `unmanaged`；非交互环境未指定策略时默认 `private`。

## 已知限制和风险

- 当前没有 session parser、memory store 或 watcher。
- 当前 trace 只覆盖 repo scan workflow；后续 eval workflow 接入时需要复用相同事件和失败语义。
- `ReadinessEvaluator` 当前信任内部 `RepoProfile` 已由 scanner 规范化；未来开放 SDK 前需要补充输入契约校验。
- README 中列出的扫描和评测能力仍属于开发中能力。
- 项目尚未确定正式 License。

## 最近完成

| 日期 | 提交 | 内容 |
| --- | --- | --- |
| 2026-05-31 | `3364e97` | 实现显式 repository initializer、托管协议块和 session log 策略 |
| 2026-05-31 | `9fa26cb` | 定义 Phase 3 有界 task report 和 session trace 模型 |
| 2026-05-31 | `1be9ad0` | 定义 Phase 3 diff、git、CI、shell 和 test 公共 evidence models |
| 2026-05-31 | `1945bb4` | 更新 workflow runtime 架构、公开输出说明和 Phase 3 下一步 |
| 2026-05-31 | `40c746c` | 补充 scan workflow 与 CLI 异常传播边界回归测试 |
| 2026-05-31 | `b75cb03` | 让 CLI 报告结构化 scan workflow 失败 |
| 2026-05-31 | `1d2a115` | 将仓库扫描接入 workflow runtime 并写出 trace |
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
