# AgentOps Harness 项目定位与边界

## 一句话定位

AgentOps Harness 是一个面向真实代码仓库的 AI coding 工作质量评测与优化 Harness。

它不负责替代 Claude Code、Codex、Cursor 或其他 coding agent 去写代码，而是观察和评估一次 AI coding 工作过程，诊断其中的上下文、验证、边界、知识沉淀问题，并将结果转化为可落地的仓库级改进资产。

## 核心问题

AI coding 的主要瓶颈不只是模型能力，也不只是工具调用能力，而是开发者很难判断和改进以下问题：

- 当前 Agent 这轮工作质量到底好不好。
- 它是否读到了正确上下文。
- 它是否偏离任务边界。
- 它是否进行了足够验证。
- 它是否因为长对话、上下文污染或任务过大开始退化。
- 仓库里的 `CLAUDE.md`、`AGENTS.md`、测试命令、约束规则是否足够支撑 Agent 稳定工作。
- 这次任务中暴露出的经验是否应该沉淀成 skill、hook、项目规则或新的工作流建议。

AgentOps Harness 要解决的是：把一次 AI coding 工作从“凭感觉判断完成”变成“可评估、可诊断、可改进、可沉淀”的工程闭环。

## 项目护城河

AgentOps Harness 的护城河不是“比 Claude Code 更会写代码”，也不是“比 Codex 更会执行任务”。

它的护城河是仓库级 AgentOps 经验资产：

- 这个仓库适合 Agent 工作的程度。
- 这个仓库的关键上下文、边界、验证命令和风险区域。
- 这个仓库中 Agent 经常失败、跑偏或漏验证的模式。
- 这个仓库应该如何编写 `CLAUDE.md`、`AGENTS.md`、skills、hooks 和任务模板。
- 每次 AI coding 过程如何转化为下一次更稳定工作的改进建议。

长期来看，项目积累的不是通用 benchmark 分数，而是“这个真实仓库如何更适合 AI coding”的可复用知识。

## 和现有工具的区别

| 工具或系统 | 主要角色 | AgentOps Harness 的区别 |
| --- | --- | --- |
| Claude Code / Codex / Cursor | 执行 coding 任务 | 不替代执行者，而是评估和优化执行过程 |
| Claude Code Review | 审查代码或 PR | 不只看最终 diff，也评估上下文、任务边界、验证、沉淀机会 |
| CI / 测试系统 | 判断代码是否通过固定检查 | 在测试之外分析 AI coding 工作流质量和仓库 Agent readiness |
| 通用 Agent benchmark | 比较模型或 Agent 的通用能力 | 聚焦单个真实仓库中的实际工作过程和长期改进 |
| 普通日志分析工具 | 汇总过程数据 | 输出可执行的仓库资产建议，如规则、skill、hook、验证门控 |

## 和传统 Harness 架构的关系

AgentOps Harness 不是教程中那种直接驱动 Agent 写代码的执行型 Harness，但它仍然属于 Harness 工程范畴。

传统执行型 Agent Harness 的核心目标是控制 Agent 如何完成任务：

```text
Observe -> Plan/Reason -> Act -> Tool Result -> Reflect -> Act again
```

AgentOps Harness 的第一阶段目标是评估和优化 AI coding 工作过程：

```text
Collect -> Normalize -> Evaluate -> Diagnose -> Recommend -> Write Artifacts
```

两者的控制对象不同：

- 执行型 Harness 控制 Agent 的任务执行过程。
- AgentOps Harness 控制 AI coding 的质量评估、风险诊断和经验沉淀过程。

因此，本项目会复用通用 Harness 的三层架构和核心工程思想，但不会照搬传统 ReAct/reflect loop。

对应关系如下：

| 通用 Harness 子系统 | AgentOps Harness 对应设计 |
| --- | --- |
| 接入层 | CLI、后续 Web UI、SDK |
| 编排层 | scan、eval、suggest、report 工作流 |
| 运行时引擎 | AgentOps workflow runtime，后续扩展 supervisory loop |
| 工具层 | repo scanner、git reader、diff parser、transcript parser、test/CI detector |
| 记忆子系统 | 仓库规则、历史评测、失败模式、skill 候选、验证习惯 |
| 模型集成与输出治理 | 评分 schema、诊断 schema、建议 schema、可选 LLM 辅助建议生成 |
| 安全层 | 只读默认、路径边界、敏感文件保护、后续干预权限控制 |
| 可观测性层 | 分析 trace、评分依据、诊断证据、报告生成日志 |

一句话：教程的 Harness 管 Agent 怎么执行；AgentOps Harness 管 AI coding 怎么被评估、诊断和持续改进。

## Workflow 与 Agent Loop 的关系

AgentOps Harness 采用分阶段架构：第一阶段以确定性 workflow 为主，后续引入监督型 Agent Loop。

第一阶段使用 workflow，是因为离线评估和仓库扫描天然适合固定流水线：

```text
Repo Scan -> Session Parse -> Evidence Normalize -> Quality Evaluate -> Diagnose -> Recommend -> Artifact Write
```

这种设计的优点是：

- 可复现。
- 可测试。
- 容易解释评分依据。
- 不容易跑偏。
- 适合先沉淀稳定的评估标准和输出格式。

后续实时旁路检测会引入 Agent Loop，但它不是 coding agent loop，而是 supervisory loop：

```text
Observe -> Detect -> Decide -> Intervene -> Learn -> Observe
```

这个监督型循环的职责是：

- 持续观察文件变化、git diff、命令输出、测试结果和 Agent 会话日志。
- 判断当前 AI coding 状态是否健康。
- 发现越界修改、长期未验证、重复失败、上下文污染、任务膨胀等风险。
- 在必要时提醒开发者验证、拆任务、压缩上下文、开启新对话或补充规则。
- 将反复出现的问题沉淀为仓库规则、skill 候选、hook 建议或验证门控。

因此，项目最终不是纯 workflow，也不是传统 ReAct Agent，而是：

```text
Workflow controls the process; supervisory loop watches the process; LLM enriches diagnosis and recommendations.
```

中文原则：

```text
确定性工作流控制主流程，监督型循环观察实时过程，模型只增强诊断和建议。
```

## 第一版范围

第一版采用 Harness Core + 最小 CLI 的形态。

核心能力包括：

1. Repo Scan
   - 扫描真实仓库结构。
   - 识别项目类型、入口文件、测试命令、CI 配置和约束文件。
   - 检查是否存在 `CLAUDE.md`、`AGENTS.md`、README、开发文档、测试说明。
   - 输出 AI coding readiness 诊断。

2. Session Eval
   - 输入一次 AI coding 工作过程材料。
   - 支持 transcript、任务描述、git diff、shell output、测试结果等离线材料。
   - 评估目标清晰度、上下文使用质量、修改边界控制、验证充分性、失败恢复情况和上下文健康度。

3. Recommendation Engine
   - 根据仓库扫描和会话评估结果生成改进建议。
   - 输出 `CLAUDE.md` / `AGENTS.md` 优化建议。
   - 提炼 skill 候选。
   - 给出 hook、验证命令、任务拆分、新对话或上下文压缩建议。

4. Artifact Writer
   - 生成 Markdown 和 JSON 结果。
   - 第一版目标产物包括：
     - `agentops-report.md`
     - `agentops-score.json`
     - `suggested-claude-md.md`
     - `suggested-agents-md.md`
     - `skill-candidates.md`

## 第一版不做什么

为避免项目跑偏，第一版明确不做：

- 不实现完整 coding agent。
- 不替代 Claude Code、Codex、Cursor 等工具。
- 不做多 Agent 横向排行榜。
- 不把“哪个工具更强”作为核心卖点。
- 不做实时旁路监控。
- 不自动修改用户仓库。
- 不只做代码 review。
- 不只输出抽象评分，必须输出可落地改进建议。

## 后续演进方向

第一版稳定后，可以逐步扩展：

- 实时旁路观察模式：监听文件变化、命令执行、测试结果和 diff。
- Claude Code hooks / Codex 工作流集成。
- 自动生成或更新 `CLAUDE.md`、`AGENTS.md` 的 patch。
- 长任务 checkpoint 和新会话建议。
- 项目级 skill 生成与验证。
- 仓库 Agent readiness 趋势报告。
- 团队级 AI coding 质量仪表盘。

## 最终形态

AgentOps Harness 的最终形态不是一个离线报告生成器，而是一个持续运行在真实仓库旁边的 AgentOps 控制层。

它应该像 CI 之于传统软件工程一样，成为 AI coding 过程中的质量基础设施：

- 在任务开始前，帮助开发者把模糊需求转成适合 Agent 执行的任务契约。
- 在任务执行中，持续观察 Agent 的上下文使用、文件改动、命令执行、验证证据和风险信号。
- 在任务即将失控时，提醒开发者拆分任务、压缩上下文、开启新对话、补充规则或收紧权限。
- 在任务完成后，评估本轮工作质量，生成可复盘报告和可复用改进资产。
- 在长期使用中，沉淀仓库级 AI coding 经验，让仓库越来越适合被 Agent 稳定维护。

从产品形态上，最终系统可以包含四层：

1. AgentOps Core
   - 负责仓库扫描、会话解析、质量评估、诊断和建议生成。
   - 保持为可测试、可嵌入、可扩展的核心库。

2. AgentOps CLI
   - 面向个人开发者和本地仓库。
   - 提供 scan、eval、suggest、report 等命令。
   - 第一版从这里开始落地。

3. AgentOps Watcher
   - 作为旁路观察进程运行。
   - 监听 git diff、文件变化、命令结果、测试输出和 Agent 会话日志。
   - 在需要时发出上下文压缩、验证、任务拆分和风险提醒。

4. AgentOps Studio
   - 面向团队和长期项目。
   - 展示仓库 Agent readiness 趋势、任务质量趋势、常见失败模式、规则沉淀情况和 skill/hook 建议。
   - 不是第一阶段目标，但代表项目的长期产品化方向。

最终系统要回答的不只是“这次 Agent 做得好不好”，而是：

- 这个仓库为什么适合或不适合 AI coding。
- 当前任务为什么让 Agent 容易失败。
- 当前对话什么时候该停止、压缩或切换。
- 哪些规则应该写进 `CLAUDE.md` / `AGENTS.md`。
- 哪些经验应该沉淀成 skill、hook、任务模板或验证门控。
- 这个仓库经过多轮 AI coding 后，是否真的变得更容易被 Agent 维护。

因此，AgentOps Harness 的长期目标是成为真实仓库的 AI coding 操作系统：不替 Agent 写代码，而是管理、评估和持续改进 Agent 在仓库中的工作方式。

## 成功标准

项目第一阶段成功的标准不是“能让 Agent 写代码”，而是：

- 能对一个真实仓库给出有用的 AI coding readiness 报告。
- 能对一次真实 AI coding 工作过程指出具体问题。
- 能解释问题原因，而不是只给分。
- 能输出可直接用于下一次 AI coding 的改进资产。
- 能让开发者更清楚地知道：该改 `CLAUDE.md`，该沉淀 skill，还是该拆任务、补测试、开新对话或压缩上下文。

## 当前决策

- 项目名称暂定为 AgentOps Harness。
- 项目主形态为 Harness Core + 最小 CLI。
- 第一版先做离线工作日志评估和真实仓库扫描。
- 实时观察、自动执行、自动修改仓库留到后续阶段。
- 项目核心卖点是 AI coding 工作质量评测与优化闭环。
