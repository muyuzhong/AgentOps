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
- 当前阶段：Phase 4 会话评测已完成（Task 1–7）。`agentops eval` 已打通确定性 scope 对账评测、eval 产物与 `eval-history.jsonl` 数据累积，意图判断的 LLM 接缝可注入但默认确定性。下一步：在同一 `IntentJudge` 接口后填充 LLM 判官，随后规划 Phase 5 仓库记忆。
- 当前版本：`0.1.0`
- 当前可用命令：
  - `agentops --help`
  - `agentops --version`
  - `agentops init --repo <repo-path>`
  - `agentops init --repo <repo-path> --session-log-policy <private|tracked|unmanaged>`
  - `agentops scan --repo <repo-path>`
  - `agentops scan --repo <repo-path> --output <output-path>`
  - `agentops check-session-log --repo <repo-path>`
  - `agentops eval --repo <repo-path>`
  - `agentops eval --repo <repo-path> --session <session.md> --diff-base <ref> --output <output-path>`
- 当前完整测试命令：

```powershell
python -m pytest -v
```

- 最近一次确认的测试结果：2026-06-04 执行 `python -m pytest -v`，共 `231 passed`，另有 1 个既有 `PytestCollectionWarning`（`TestResult` dataclass 名称被 pytest 尝试收集）。

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
- 已完成 Task 4 init CLI：
  - `agentops init --repo <repo-path>`
  - `agentops init --repo <repo-path> --session-log-policy <private|tracked|unmanaged>`
- 显式策略跳过提示；未显式指定策略时，非交互 stdin 默认使用 `private`，交互式 stdin 提供三项编号选择。
- CLI 仅将 initializer 的 `ValueError` 转换为简短初始化错误；意外异常继续向上传播。
- 已完成 Task 5 unified diff parser：
  - `DiffParser`
- diff parser 只解析输入文本，不调用 git；按源顺序输出修改、新增、删除、重命名和二进制文件证据。
- 行数只在 `@@` hunk 内统计，忽略文件 header、上下文行和 `\ No newline at end of file`。
- 已处理真实 Git 路径边界：空格、路径内嵌 ` b/`、quoted UTF-8 八进制转义，以及 rename 元数据解码。
- 已完成 Task 6 只读 GitAnalyzer：
  - `GitAnalysisError`
  - `GitAnalyzer`
- GitAnalyzer 仅执行受控只读命令：`git rev-parse --show-toplevel`、`git branch --show-current`、`git status --porcelain=v1 --untracked-files=all` 和 `git diff --find-renames --no-ext-diff --unified=0 HEAD`。
- `status()` 返回排序后的 POSIX 风格相对路径，并处理 quoted UTF-8 八进制路径、rename 引号外箭头切分、quoted POSIX 字面反斜杠和未 quoted Windows 风格分隔符。
- `diff()` 复用 `DiffParser` 返回规范化 diff evidence；Git 子进程统一使用 UTF-8、`shell=False`，并将启动或命令失败封装为 `GitAnalysisError`。
- 已完成 Task 7 只读 CIDetector：
  - `CIScanError`
  - `CIDetector`
- CIDetector 只读已知 CI 路径（GitHub Actions、GitLab CI、Azure Pipelines），用 `yaml.safe_load` 保守提取验证命令：GitHub `jobs.*.steps[*].run`、GitLab 顶层与作业级 `before_script/script/after_script`、Azure `steps[*]` 与 `jobs[*].steps[*]` 的 `script/bash/powershell`。
- 命令按配置文件排序提取，多行拆分、去空白、全局去重并保留首次出现顺序；不展开变量、不执行、不跟随 include。已为 `RepoProfile` 增加 `validation_commands` 并接入 `RepoScanner`，保持 `ci_files` 行为稳定。新增 `PyYAML>=6.0` 运行时依赖。
- 已完成 Task 8 ShellOutputParser：
  - `ShellOutputParser`
- shell 成功只看退出码；摘要有界（`MAX_SHELL_SUMMARY_CHARS = 4000`），超出时保留首尾并插入确定性截断标记；两个流都有内容时加 `[stdout]`/`[stderr]` 标签。
- 从完整未截断输出中保守识别 pytest 终端汇总（passed/failed/skipped/errors）为 `TestResult`；不匹配受支持格式时保持 unknown（`test_result is None`）。
- 已完成 Task 9 TranscriptParser：
  - `TranscriptParseError`
  - `TranscriptParser`
- TranscriptParser 增量解析 `.agentops/agentops-session.md`，校验必需章节（Goal/Changes/Verification）与 Command/Result 配对，拒绝重复章节和孤立 Command/Result。
- 应用显式有界限额（`MAX_TASKS = 100`、`MAX_TASK_BYTES = 16384`、`MAX_FIELD_CHARS = 2000`、`MAX_LIST_ITEMS = 50`），命中限额时显式标记 truncated；只保留最新 MAX_TASKS 条并维持源顺序。
- 绝不对整份日志调用 `read_text`，也绝不打开 Evidence References 指向的原始 transcript（按不透明指针保留）。

### Phase 3.5：Eval Spike

- 已实现最小 stop-hook（保留特性）：
  - `SessionLogState`
  - `SessionLogCheck`
  - `check_session_log`
- `check_session_log` 对比任务日志与 `.agentops/.session-log-state.json` 记录的基线：字节变多且 sha256 改变才算有新追加，缺少基线一律提醒；每次都刷新基线，状态文件原子写入。task_count 复用有界 TranscriptParser，绝不打开原始 transcript，日志非法时退化为 0。
- 已暴露 `agentops check-session-log --repo`：有新追加退出 0 且安静，否则把提醒写到 stderr 并以非零码退出；缺失仓库给出简短错误。
- 已实现 scope-drift 对账探针（throwaway，验证用）：
  - `ScopeDriftFinding`
  - `ScopeDriftReport`
  - `reconcile_scope`
- `reconcile_scope` 用纯确定性规则对账 `TaskReport`（声明）与 `DiffSummary`（真相）：undeclared_change、declared_not_changed、cross_module_breadth；并以单条 `intent_alignment`（`llm_needed=True`）标出意图判断必须交给 LLM 的位置，不调用任何 LLM。
- 已在真实 git working tree 上跑通整条链路（TranscriptParser → GitAnalyzer → reconcile_scope），结论写入 `docs/superpowers/findings/2026-06-03-scope-drift-spike.md`。Task 3（init 自动注册 stop-hook）按计划推迟，改为在 findings 文档记录手动接线方式。

### Phase 4：Session Eval

- 已完成 Task 1 changed-files declaration：
  - `TaskReport.changed_files`
  - `TranscriptParser` 解析可选 `### Changed Files`
  - `reconcile_scope` 优先使用显式 changed files，缺失时回退到 changes 自由文本路径抽取。
- 已完成 Task 2 configurable diff base：
  - `GitAnalyzer.diff(repo_path, base="HEAD")`
- diff base 默认仍是 `HEAD`；显式 base 作为受控 git 参数传入，拒绝空值、空白、option-like 和包含控制字符的 ref。
- 已完成 Task 3 deterministic session-eval scoring and intent seam：
  - `EvalResult`
  - `IntentVerdict`
  - `ScopeEvaluation`
  - `evaluate_scope`
  - `IntentJudge`
  - `DeterministicIntentJudge`
- `evaluate_scope` 只对确定性 scope findings 扣分，跳过 `llm_needed=True` 的 `intent_alignment`；每个扣分 finding 都带 evidence 和可执行 `Recommendation`，score 下限为 `0`。
- `DeterministicIntentJudge` 是 Phase 4 默认意图判官：只对 `llm_needed=True` 且 `code == "intent_alignment"` 的 finding 产出 `needs_review` / `source="deterministic"` 裁决，不调用 LLM、网络或 API key。
- 已完成 Task 4 eval workflow runtime：
  - `EvalRunResult`
  - `EvalWorkflowError`
  - `run_eval`
- `run_eval` 通过 `WorkflowRunner` 串联 parse_session → select_task → collect_diff → reconcile_scope → judge_intent → build_eval_result → write_eval_artifacts，评估最新一条任务报告；缺失会话和空日志降级为结构化 `EvalWorkflowError`，并复用与 scan 相同的 trace 事件/失败语义。
- 已完成 Task 5 eval artifacts/history：
  - `EvalReportWriter`
  - `ArtifactKind.EVAL_HISTORY`
- `EvalReportWriter` 写出 `agentops-report.md`（声明 vs 改动、发现、建议、意图裁决）、`agentops-score.json`（镜像 `EvalResult.to_dict()`），并向 append-only 的 `eval-history.jsonl` 追加一行带注入时间戳的记录；markdown/json 覆盖写出、历史只追加。
- 已完成 Task 6 `agentops eval` CLI：
  - `agentops eval --repo <repo-path> [--session <md>] [--diff-base <ref>] [--output <dir>]`
- `--session` 默认 `<repo>/.agentops/agentops-session.md`，`--diff-base` 默认 `HEAD`；结构化 `EvalWorkflowError`（缺失仓库/会话、空日志）返回退出码 1、stderr 简短信息且无 traceback，意外异常不被隐藏；`scan`/`init`/`check-session-log` 行为保持不变。
- 已完成 Task 7 Phase 4 文档收口与真实验证：对本仓库执行 `agentops eval --repo . --diff-base 42ac100`，声明与 git 真相一致得 `100/100`，写出四个产物，且评测前后 tracked 工作区保持干净（对目标仓库只读）。

## 当前文件边界

| 路径 | 职责 |
| --- | --- |
| `agentops/cli.py` | CLI 入口和 `scan` / `init` / `check-session-log` / `eval` 子命令薄适配器 |
| `agentops/core/repo.py` | 仓库画像模型 |
| `agentops/core/evaluation.py` | Finding 和 ReadinessReport |
| `agentops/core/eval.py` | 会话评测结果模型和 intent verdict 模型 |
| `agentops/core/recommendation.py` | 建议类型和建议模型 |
| `agentops/core/artifact.py` | 输出产物模型 |
| `agentops/core/evidence.py` | diff、git、CI、shell 和 test 公共证据模型 |
| `agentops/core/session.py` | 有界任务日志的 session 证据模型 |
| `agentops/core/workflow.py` | workflow 状态、事件、失败和 trace 模型 |
| `agentops/initializers/repo.py` | 显式安装 session protocol、托管指令块和 session log 策略 |
| `agentops/analyzers/git.py` | 通过受控只读 Git 子进程采集 branch、status 和规范化 diff |
| `agentops/parsers/diff.py` | 将 unified git diff 规范化为公共 diff evidence models |
| `agentops/parsers/shell_output.py` | 有界 shell 输出摘要与 pytest 摘要识别 |
| `agentops/parsers/transcript.py` | 有界 agentops-session.md 任务日志解析为 SessionTrace |
| `agentops/scanners/repo.py` | 只读仓库扫描与测试命令推断 |
| `agentops/scanners/ci.py` | 只读 CI 配置检测与保守验证命令提取 |
| `agentops/evaluators/readiness.py` | 确定性 readiness 扣分规则 |
| `agentops/evaluators/scope_drift.py` | Phase 3.5 scope-drift 对账探针（声明 vs 真相） |
| `agentops/evaluators/session_eval.py` | 将 scope-drift 对账结果转换为确定性 score、findings 和 recommendations |
| `agentops/judges/intent.py` | intent judge 协议和确定性默认判官 |
| `agentops/hooks/session_log.py` | 会话日志新鲜度检查（stop-hook 核心） |
| `agentops/writers/report.py` | Markdown 和 JSON readiness 产物写出 |
| `agentops/writers/eval_report.py` | eval 报告、评分和 append-only 历史产物写出 |
| `agentops/writers/trace.py` | JSON workflow trace 产物写出 |
| `agentops/runtime/scan.py` | scan workflow 编排、trace 写出和结构化失败 |
| `agentops/runtime/eval.py` | session-eval workflow 编排、产物/trace 写出和结构化失败 |
| `agentops/runtime/workflow.py` | 同步确定性 workflow runner |
| `tests/test_cli.py` | CLI 行为测试 |
| `tests/test_core_models.py` | 核心模型测试 |
| `tests/test_evidence_models.py` | Phase 3 公共 evidence models 测试 |
| `tests/test_session_models.py` | Phase 3 有界 session models 测试 |
| `tests/test_repo_initializer.py` | Phase 3 repository initializer 测试 |
| `tests/test_git_analyzer.py` | Phase 3 只读 GitAnalyzer 测试 |
| `tests/test_diff_parser.py` | Phase 3 unified diff parser 测试 |
| `tests/test_ci_scanner.py` | Phase 3 CIDetector 测试 |
| `tests/test_shell_output_parser.py` | Phase 3 ShellOutputParser 测试 |
| `tests/test_transcript_parser.py` | Phase 3 TranscriptParser 测试 |
| `tests/test_session_log_hook.py` | Phase 3.5 会话日志 stop-hook 测试 |
| `tests/test_scope_drift.py` | Phase 3.5 scope-drift 对账测试 |
| `tests/test_eval_models.py` | Phase 4 eval result 和 intent verdict 模型测试 |
| `tests/test_session_eval.py` | Phase 4 deterministic scope scoring 测试 |
| `tests/test_intent_judge.py` | Phase 4 intent judge seam 测试 |
| `tests/test_eval_runtime.py` | Phase 4 session-eval workflow 集成测试 |
| `tests/test_eval_report_writer.py` | Phase 4 eval 报告、评分与历史写出测试 |
| `tests/test_repo_scanner.py` | 仓库扫描器测试 |
| `tests/test_readiness_evaluator.py` | readiness 评分规则测试 |
| `tests/test_report_writer.py` | readiness 产物写出测试 |
| `tests/test_scan_runtime.py` | scan 流水线集成测试 |

## 下一步

Phase 4 会话评测已全部完成（Task 1–7）。下一步：先为 LLM-backed `IntentJudge` 写一份新的纵向切片实施计划，再在现有 `IntentJudge` 接口后填充 LLM 判官——保持同一接口、测试中打桩、默认路径仍不触达网络/API key——判断 scope 差值是否落在任务意图之内。随后基于累积的 `eval-history.jsonl` 规划 Phase 5 仓库记忆：

```text
docs/superpowers/plans/
```

实施前依次阅读 `agent.md`、本文档和 `docs/development-roadmap.md`，确认下一阶段边界；每次只完成一个 Task，先写失败测试再写最小实现。

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
- agent 自述的 session md 定位为"声明"（declaration），不是"真相"。评估核心逻辑是拿声明和 ground truth（git diff、exit code）对账，差值才是诊断信号。这个原则决定了 Watcher 的机制设计和 Phase 4 的评估架构。
- 确定性规则在 readiness（文件存在性）上有效，但在会话质量评估上的天花板尚不明确。需要通过纵向探针（spike）验证后才能定 Phase 4 架构，而不是凭假设设计。
- Phase 3 引入 `PyYAML>=6.0` 作为运行时依赖，仅用于 `yaml.safe_load` 解析受支持的 CI 配置；CI 命令提取保持保守，不实现通用 workflow 引擎、不展开变量、不执行命令。
- CIDetector、ShellOutputParser、TranscriptParser 只采集和解析证据，不评分、不诊断、不调用 LLM；评分留到 Phase 3.5 及之后。
- Phase 3.5 探针结论：确定性规则可靠覆盖"文件集合"层的 scope drift；意图判断（差值是否属于任务意图）是天花板，必须由 LLM 承担。Phase 4 把确定性对账作为第一道，LLM 只在 intent_alignment 处介入；并升级任务日志协议增加显式 `### Changed Files`、支持可配置 diff base。
- Phase 4 会话评测复用确定性 `reconcile_scope` + `evaluate_scope` 作为第一道，唯一 LLM 接缝是 `IntentJudge.judge`（默认 `DeterministicIntentJudge` 给 `needs_review`、不触达模型）；workflow 控制流程，LLM 只增强意图裁决。`run_eval` 评估最新一条任务报告，eval 历史以 append-only `eval-history.jsonl` 累积——先存数据，Phase 5 再读，不在 Phase 4 实现记忆系统。`agentops eval` 对目标仓库只读，仅向 `--output` 写产物。

## 已知限制和风险

- session-eval workflow 已接入并复用 scan 的 trace 事件/失败语义；但意图裁决仍是确定性占位（`needs_review`），尚无 LLM 判官，也仍没有 memory store 或 watcher。
- `agentops eval` 默认 `--diff-base HEAD` 只对账工作区相对 HEAD 的 tracked 改动，不含 untracked 文件；需要纳入未跟踪文件或历史区间时需显式传 `--diff-base`。
- session-eval 的 scope-discipline 扣分权重（undeclared 15 / declared_not_changed 10 / cross_module 10）与 readiness 权重一样是 provisional，缺乏真实数据支撑，后续需用累积的 eval 历史校准。
- `ReadinessEvaluator` 当前信任内部 `RepoProfile` 已由 scanner 规范化；未来开放 SDK 前需要补充输入契约校验。
- README 中列出的诊断和改进资产生成能力仍属于开发中能力。
- 项目尚未确定正式 License。
- 当前 readiness 评分是文件存在性检查，不是质量检查（有 `CLAUDE.md` 不等于 `CLAUDE.md` 有用）。权重（15/25/25/15/10/10）缺乏依据，需要在后续版本中升级为质量评估。
- `WorkflowRunner` 已同时承载 scan 与 eval 两条流水线；若后续 LLM-in-the-loop 需要非确定性编排，可能需要扩展或返工。

## 最近完成

| 日期 | 提交 | 内容 |
| --- | --- | --- |
| 2026-06-04 | `1960990` | 暴露 `agentops eval` 会话评测命令 |
| 2026-06-04 | `06a1afd` | 写出 session-eval 报告、评分与 append-only 历史 |
| 2026-06-04 | `08330ef` | 通过 WorkflowRunner 运行 session-eval 流水线 |
| 2026-06-04 | `1b954a3` | 实现确定性 session-eval scoring、EvalResult 和 intent judge seam |
| 2026-06-03 | `4ae27b8` | 支持可配置 git diff base |
| 2026-06-03 | `80b236f` | 在任务日志协议中显式声明 changed files |
| 2026-06-03 | `f82a196` | scope-drift 对账探针（确定性，标注 LLM 介入点） |
| 2026-06-03 | `9869ea0` | 暴露 agentops check-session-log 新鲜度命令 |
| 2026-06-03 | `cc96a49` | 检测会话日志是否有新追加（stop-hook 核心） |
| 2026-06-03 | `559e863` | 记录 Phase 3 分析工具完成与 Phase 3.5 下一步 |
| 2026-06-03 | `b6587ec` | 解析有界 agentops-session.md 任务日志为 SessionTrace |
| 2026-06-03 | `20affc8` | 解析有界 shell 输出与 pytest 摘要为 ShellResult |
| 2026-06-03 | `b4c2c0f` | 检测 CI 配置并保守提取验证命令 |
| 2026-06-02 | `5c13ac7` | 通过受控只读 Git 子进程采集 branch、status 和规范化 diff evidence |
| 2026-06-01 | `4907947` | 解析 unified git diff 并规范化真实 Git 路径边界 |
| 2026-06-01 | `4ef112a` | 暴露 `agentops init` CLI 和交互式 session log policy 解析 |
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
