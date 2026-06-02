# AgentOps Harness 开发上下文

本文档用于让后续参与开发的 AI coding agent 快速理解项目定位、边界和构建顺序。

## 每次任务开始前

按顺序执行：

1. 阅读本文档。
2. 阅读 `docs/project-memory.md`，获取当前阶段、已完成能力、已知限制和下一步。
3. 阅读与当前任务相关的设计文档和实施计划。
4. 运行 `git status --short`，确认工作区状态。
5. 运行 `python -m pytest -v`，确认基线测试。

涉及并行开发时，先阅读 `docs/development-roadmap.md`，并使用 `.worktrees/` 创建独立 worktree。

## 项目定位

AgentOps Harness 是一个面向真实代码仓库的 AI coding 工作质量评测与优化 Harness。

它不替代 Claude Code、Codex、Cursor 或其他 coding agent 写代码，而是评估一次 AI coding 工作过程，诊断上下文、验证、边界、任务拆分和知识沉淀问题，并生成可落地的仓库级改进资产。

核心闭环：

```text
Observe -> Evaluate -> Diagnose -> Improve
```

- Observe：采集仓库结构、任务描述、transcript、diff、shell output、测试结果等材料。
- Evaluate：评估当前 Agent 工作质量。
- Diagnose：解释问题原因，而不是只给分。
- Improve：输出 `CLAUDE.md` / `AGENTS.md` 建议、skill 候选、hook 建议、验证命令和工作流建议。

## 架构原则

本项目不是传统执行型 Agent Harness，但仍然属于 Harness 工程。

传统执行型 Harness 控制 Agent 如何完成任务：

```text
Observe -> Plan/Reason -> Act -> Tool Result -> Reflect -> Act again
```

AgentOps Harness 控制 AI coding 工作如何被评估、诊断和持续改进：

```text
Collect -> Normalize -> Evaluate -> Diagnose -> Recommend -> Write Artifacts
```

第一阶段采用确定性 workflow：

```text
Repo Scan -> Session Parse -> Evidence Normalize -> Quality Evaluate -> Diagnose -> Recommend -> Artifact Write
```

后续实时旁路检测会引入监督型 Agent Loop：

```text
Observe -> Detect -> Decide -> Intervene -> Learn -> Observe
```

这个 loop 不是 coding agent loop。它不负责直接写代码，而是观察 AI coding 过程，发现风险并给出干预建议。

核心原则：

```text
Workflow controls the process; supervisory loop watches the process; LLM enriches diagnosis and recommendations.
```

中文原则：

```text
确定性工作流控制主流程，监督型循环观察实时过程，模型只增强诊断和建议。
```

### 声明 vs 真相

评估的核心不是"复述 agent 做了什么",而是"对账 agent 声称的和实际发生的"。

- **声明（declaration）**:agent 自述的 session md——它声称做了什么、改了什么、验证了什么。agent 可以伪造。
- **真相（ground truth）**:git diff、命令退出码、测试结果。agent 无法伪造。

两者之间的差值才是诊断的核心信号。例如:md 说"只改了 login,无其他改动",diff 却显示 8 个文件横跨 3 个模块——这不仅是范围漂移,更是 agent 的自我认知失败。

写 session md 时要诚实、要包含失败记录,因为 md 会被拿去和 diff/exit code 对账。

## 不要做什么

本项目第一阶段明确不做：

- 不实现完整 coding agent。
- 不替代 Claude Code、Codex、Cursor。
- 不做多 Agent 横向排行榜。
- 不把“哪个 Agent 更强”作为核心卖点。
- 不只做代码 review。
- 不自动修改用户仓库。
- 不做实时旁路监控，实时 watcher 留到后续阶段。
- 不输出空泛评分，必须输出可落地改进建议。

## 构建参照

项目学习和构建顺序参考：

```text
D:\harness agent\harness_engineering_guide
```

尤其参考该教程中 MiniHarness 的构建节奏，但不要照抄 MiniHarness。MiniHarness 是一个通用 Agent Harness；本项目是 AgentOps Harness。

教程顺序与本项目映射：

| 教程阶段 | MiniHarness 内容 | AgentOps Harness 对应内容 |
| --- | --- | --- |
| 第 2 章 | 核心接口和脚手架 | 核心数据模型和 CLI 骨架 |
| 第 4 章 | Agent runtime loop | AgentOps 评测流水线 runtime |
| 第 5 章 | 工具注册和执行 | repo scanner、diff reader、transcript parser 等分析工具 |
| 第 6 章 | 记忆系统 | 仓库经验记忆、历史评测、失败模式、规则沉淀 |
| 第 7 章 | 模型集成与输出治理 | 结构化评分、诊断规则、报告 schema、可选 LLM 辅助建议 |
| 第 8 章 | 编排引擎 | scan/eval/suggest/report 工作流编排 |
| 第 9 章 | MCP 集成 | 后续接 Claude Code、Codex、外部日志源或 MCP 工具 |
| 第 10 章 | 生产化 | 配置、插件、模板、特性门控 |
| 第 11 章 | 可靠性 | 日志、追踪、健康检查、失败恢复 |
| 第 12 章 | 安全 | 路径校验、只读默认策略、危险操作防护 |
| 第 13 章 | 测试评估 | fixture 仓库、模拟 transcript、golden report、评分一致性测试 |

## 第一阶段目标

第一阶段采用 Harness Core + 最小 CLI。

优先实现：

1. Core models
   - `RepoProfile`
   - `SessionTrace`
   - `EvalResult`
   - `Recommendation`
   - `Artifact`

2. Repo Scan
   - 扫描真实仓库结构。
   - 识别项目类型、测试命令、CI 配置和约束文件。
   - 输出 AI coding readiness 诊断。

3. Artifact Writer
   - 生成 Markdown 和 JSON 结果。
   - 第一版至少生成 `agentops-report.md`。

第一个可运行命令：

```bash
agentops scan --repo <repo-path>
```

第二个目标命令：

```bash
agentops eval --repo <repo-path> --transcript session.md --diff changes.diff
```

## 建议目录结构

第一阶段建议结构：

```text
agentops_harness/
  agent.md
  docs/
    positioning-and-boundaries.md
  agentops/
    core/
      repo.py
      session.py
      evaluation.py
      recommendation.py
      artifact.py
    runtime/
    scanners/
    parsers/
    evaluators/
    recommenders/
    writers/
    cli.py
  tests/
  pyproject.toml
```

目录职责：

- `core/`：项目公共数据模型和类型定义。
- `runtime/`：评测流水线和工作流执行。
- `scanners/`：仓库扫描、CI 检测、测试命令识别。
- `parsers/`：transcript、diff、shell output、测试结果解析。
- `evaluators/`：评分和质量评估规则。
- `recommenders/`：生成改进建议。
- `writers/`：写出 Markdown、JSON 和建议草案。
- `tests/`：单元测试、fixture 仓库、golden report。

## 输出资产

第一版目标产物：

- `agentops-report.md`
- `agentops-score.json`
- `suggested-claude-md.md`（诊断结果：缺什么、多什么、哪些该精简,不是最终文本）
- `suggested-agents-md.md`（同上）
- `skill-candidates.md`
- `eval-history.jsonl`（每次 eval 的诊断结果追加,用于趋势分析和 Phase 5 记忆系统）

其中 `agentops-report.md` 是第一优先级。

## 开发原则

- 先做结构化数据，再做自然语言报告。
- 代码中要明确包含中文注释
- 先做确定性规则，再引入 LLM 辅助建议。
- `CLAUDE.md` 优化不只是"加内容",也包括"做减法"。`CLAUDE.md` 每轮对话都会注入上下文,内容过多会挤占有效 token。优化目标是保持在 200 行以内,只保留项目特定的约束、验证命令和边界。AgentOps 输出诊断（缺什么、多什么、哪些该精简）,不直接生成最终文本；实际改写由 coding agent 通过 skill 形式的优化指南完成,优化指南通过渐进式披露按需加载。
- 先做只读扫描和离线评估，再做自动修改。
- 先支持单仓库、单会话，再扩展历史趋势和团队视图。
- 每个阶段都必须能解释“这个能力如何让 AI coding 更稳定”。
- 如果一个功能只是让项目看起来像普通 coding agent，应推迟或删除。
- 当架构里存在未验证的关键假设时，用纵向探针（spike）提前验证：只切一个维度，打穿所有层，目的是验证假设而不是交付功能。探针可以硬编码、可以走捷径、验证完可以扔。基于探针答案定架构,不凭假设设计。

## 当前下一步

Phase 3 analysis tools 已完成：仓库初始化、公共 evidence/session 模型、unified diff parser、只读 GitAnalyzer、CIDetector、ShellOutputParser、TranscriptParser 全部落地，`python -m pytest` 共 171 passed。

下一步进入 Phase 3.5 纵向探针:用现有的 `TaskReport` + `DiffSummary`,实现一个维度的会话评估（scope drift）,纯确定性规则,标出"这里该插 LLM"的位置。探针同时验证两个假设：确定性规则在会话质量上能走多远；"agent 声明 vs diff 真相"对账机制是否跑得通。进入该阶段前先写一份 Phase 3.5 实施计划。

实施时依次执行：

1. 阅读 `docs/project-memory.md`。
2. 阅读 `docs/development-roadmap.md`，确认下一阶段边界。
3. 先编写 Phase 3.5 纵向探针实施计划，再按计划执行。

每次只完成计划中的一个 Task，先写失败测试，再写最小实现，然后运行测试并提交。不要一次实现后续 Phase 的能力。

## 每次任务完成后

1. 运行相关测试和完整测试。
2. 将功能合并到 `main`。
3. 更新 `docs/project-memory.md` 中的当前状态、最近完成、下一步和已知风险。
4. 确认集中记忆已更新后再推送远程。

并行 worktree 不直接修改 `docs/project-memory.md`。集中记忆由集成者在合并后更新，避免冲突和事实分叉。
