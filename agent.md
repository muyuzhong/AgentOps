# AgentOps Harness 开发上下文

本文档用于让后续参与开发的 AI coding agent 快速理解项目定位、边界和构建顺序。进入项目后，请先阅读本文档，再阅读 `docs/positioning-and-boundaries.md`。

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
- `suggested-claude-md.md`
- `suggested-agents-md.md`
- `skill-candidates.md`

其中 `agentops-report.md` 是第一优先级。

## 开发原则

- 先做结构化数据，再做自然语言报告。
- 代码中要明确包含中文注释
- 先做确定性规则，再引入 LLM 辅助建议。
- 先做只读扫描和离线评估，再做自动修改。
- 先支持单仓库、单会话，再扩展历史趋势和团队视图。
- 每个阶段都必须能解释“这个能力如何让 AI coding 更稳定”。
- 如果一个功能只是让项目看起来像普通 coding agent，应推迟或删除。

## 当前下一步

下一步应按教程第 2 章的方式推进：

1. 创建 Python 项目脚手架。
2. 定义 `core/` 数据模型。
3. 搭建最小 CLI。
4. 实现 `agentops scan --repo <repo-path>` 的最小版本。
5. 增加测试，验证核心模型和仓库扫描输出。

实施时依次执行：

1. `docs/superpowers/plans/2026-05-30-phase-0-core-scaffold.md`
2. `docs/superpowers/plans/2026-05-30-phase-1-minimal-repo-scan.md`

每次只完成计划中的一个 Task，先写失败测试，再写最小实现，然后运行测试并提交。不要一次实现后续 Phase 的能力。
