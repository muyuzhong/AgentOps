# AgentOps Harness

[English](README.en.md)

AgentOps Harness 是一个面向真实代码仓库的 AI coding 工作质量评测与优化系统。

Claude Code、Codex、Cursor 等工具可以执行开发任务。AgentOps Harness 关注这些工具在真实仓库中的工作质量：它观察工作过程，解释问题原因，并将一次开发中的经验沉淀为可复用的仓库资产。

它帮助你回答：

- 当前 Agent 是否读取了正确上下文。
- 修改是否超出任务边界。
- 验证证据是否充分。
- 长对话是否开始退化。
- 哪些规则应该写进 `CLAUDE.md` 或 `AGENTS.md`。
- 哪些重复经验应该提炼为 skill、hook、测试命令或工作流建议。

## 工作原理：声明 vs 真相

AgentOps 的评估核心不是“复述 Agent 做了什么”，而是“对账 Agent 声称的和实际发生的”：

- **声明**：Agent 自述的会话日志——它声称做了什么、改了什么、验证了什么。Agent 可以伪造。
- **真相**：git diff、命令退出码、测试结果。Agent 无法伪造。

两者之间的差值才是诊断的核心信号。例如：日志说“只改了登录逻辑”，diff 却显示 8 个文件横跨 3 个模块——这既是范围漂移，也是 Agent 的自我认知失败。

## 功能

已经可用：

- **仓库就绪度扫描**：识别项目结构、测试命令、CI 配置（含验证命令）和 Agent 约束文件，输出 readiness 评分和可执行建议。
- **仓库初始化**：安装会话协议，向 `CLAUDE.md` / `AGENTS.md` 写入托管指令块，约定 Agent 如何记录工作日志。
- **会话评测（scope 维度）**：对账最新一条任务报告的声明与 git 真相，输出确定性的 scope-discipline 评分、带证据的发现和可执行建议，并把每次评测追加进 `eval-history.jsonl`。
- **意图裁决（可选 LLM）**：`--intent-judge llm` 对每条确定性漂移发现逐条裁决“在意图内 / 真正越界”（`within_intent` / `drift`）；默认仍是离线、确定性的 `needs_review`，任何失败都自动降级。裁决只丰富报告，不改变确定性分数。
- **仓库记忆（确定性投影）**：`agentops memory` 把累积的 `eval-history.jsonl` 蒸馏为仓库记忆——分数/漂移趋势、反复出现的失败模式（各带「N/M 次评测复现」证据）、带证据的规则候选和 skill 候选。记忆是历史的可再生投影：同样历史产出字节一致的记忆，离线、确定性，不移动任何评测分数。
- **改进资产（确定性投影）**：`agentops suggest` 把仓库记忆 + 现有指令文件投影为可直接采纳的改进资产——`CLAUDE.md` / `AGENTS.md` 的 `agentops:repo-rules` 托管块（加法）与精简诊断（减法：超长、重复 README）、按反复失败模式映射现有命令的 hook 提案（含 `settings.json` 片段），以及工作流指引与 skill 脚手架。对目标仓库只读（绝不改写指令文件），离线、可再生、不移动分数。
- **工作流追踪**：记录确定性的扫描和评测步骤及失败信息，便于检查执行过程。

开发中：

- **更多评测维度**：在 scope/boundary 之外，增加上下文质量、验证充分性等维度。
- **问题诊断**：识别上下文缺失、修改越界、验证不足、重复失败和任务膨胀。
- **实时旁路监督**：观察 AI coding 过程、发现风险并给出干预建议（Phase 7）。

## 安装

要求 Python 3.11 或更高版本。

```shell
git clone https://github.com/muyuzhong/AgentOps.git
cd AgentOps
python -m pip install -e .
```

## 使用方式

项目处于早期开发阶段。目前可以查看 CLI、初始化仓库会话协议，并扫描仓库 readiness：

```shell
agentops --help
agentops --version
```

### 初始化仓库

`agentops init` 是显式写操作。它写入 `.agentops/session-protocol.md` 和 `.agentops/agentops-session.md`，并向已有的 `CLAUDE.md`、`AGENTS.md` 追加托管协议块；两者都不存在时创建 `rule.md`。

```shell
agentops init --repo <repo-path>

# 选择会话日志策略：private（默认）、tracked 或 unmanaged
agentops init --repo <repo-path> --session-log-policy <private|tracked|unmanaged>
```

### 扫描仓库

```shell
# 扫描仓库的 AI coding readiness
agentops scan --repo <repo-path>

# 默认写入当前目录下的 .agentops/，也可以指定输出目录
agentops scan --repo <repo-path> --output <output-path>
```

### 评测一次会话

`agentops eval` 评测最新一条任务报告：对账声明与 git 真相，输出确定性的 scope-discipline 评分、带证据的发现、可执行建议和意图裁决，并把本次评测追加进 `eval-history.jsonl`。它对目标仓库只读，只向 `--output` 目录写入产物。

```shell
# 评测最新任务报告（声明 vs 工作区相对 HEAD 的 diff）
agentops eval --repo <repo-path>

# --session 默认 <repo>/.agentops/agentops-session.md；--diff-base 默认 HEAD（任意 git ref 均可）
agentops eval --repo <repo-path> --session <session.md> --diff-base <ref> --output <output-path>
```

意图判断的 LLM 接缝已经就位但默认不调用模型：确定性默认判官把每个 `intent_alignment` 标为 `needs_review`，整条默认路径无需 API key、无网络调用。

### 可选：用 LLM 做意图裁决

默认 `agentops eval` 完全离线、确定性，不需要任何 API key。加上 `--intent-judge llm` 后，每条确定性漂移发现都会交给模型逐条裁决“在意图内还是真正越界”：

```shell
# 设置 OpenAI 兼容端点的 API key（默认端点为 mimo，可用 --intent-base-url / AGENTOPS_LLM_BASE_URL 覆盖）
$env:AGENTOPS_LLM_API_KEY = "<your-key>"           # PowerShell
agentops eval --repo <repo-path> --intent-judge llm --intent-model mimo-v2.5-pro
```

- `--intent-judge` 默认 `deterministic`（Phase 4 行为）；设为 `llm` 才启用模型。
- `--intent-model` 选择模型 id；`--intent-base-url` / `AGENTOPS_LLM_BASE_URL` 覆盖端点；key 从环境变量 `AGENTOPS_LLM_API_KEY` 读取。
- 缺 key、缺 model、网络故障或响应不可解析时，判官自动降级为确定性 `needs_review`，评测照常以退出码 0 完成，并在 stderr 打印一行降级说明。
- LLM 裁决只丰富报告（按 `drift` / `within_intent` / `needs_review` 分组并标注来源），**不改变**确定性 scope 分数。
- 适配器仅用标准库 HTTP 调 OpenAI 兼容接口，不引入任何新依赖（`import agentops` 无需任何第三方 SDK）。

### 沉淀仓库记忆

`agentops memory` 把累积的 `eval-history.jsonl` 确定性地投影为仓库记忆：逐行读历史（容忍空行、坏行，以及早期缺少裁决摘要的旧行），蒸馏出分数/漂移**趋势**、反复出现的**失败模式**、带证据的**规则候选**和 **skill 候选**，并覆盖写出记忆产物。它对目标仓库只读，只向 `--output` 目录写入；离线、确定性，不调用任何模型、不需 API key、零新增依赖。

```shell
# 把累积评测历史蒸馏为仓库记忆
agentops memory --repo <repo-path>

# --history 默认 <repo>/.agentops/eval-history.jsonl；--output 默认 .agentops
agentops memory --repo <repo-path> --history <eval-history.jsonl> --output <output-path>
```

- 每个反复出现的失败模式都标注「在 N/M 次评测中复现」、热点路径和最近出现时间；规则候选与 skill 候选引用同一历史证据。
- 记忆是历史的**可再生投影**：同样的历史产出字节一致的记忆，每次运行覆盖重写（绝不 append），`eval-history.jsonl` 仍是唯一真相来源。
- 记忆只**读取**评测分数来计算趋势，从不重算或写回任何分数；是否让漂移趋势校准分数留待后续依累积数据再定。
- 还没有跑过任何评测（历史缺失或为空）时，命令以结构化错误退出（退出码 1，提示先跑 `agentops eval`，无 traceback）。

### 生成改进资产

`agentops suggest` 把累积的 `eval-history.jsonl` 重新投影为仓库记忆，再只读地读取仓库当前的 `CLAUDE.md` / `AGENTS.md` / `README.md`，把记忆 + 指令文件确定性地投影为**可直接采纳的改进资产**并覆盖写出。它对目标仓库只读，只向 `--output` 目录写入；离线、确定性，不调用任何模型、不需 API key、零新增依赖。

```shell
# 把累积记忆投影为可采纳的改进资产
agentops suggest --repo <repo-path>

# --history 默认 <repo>/.agentops/eval-history.jsonl；--output 默认 .agentops
agentops suggest --repo <repo-path> --history <eval-history.jsonl> --output <output-path>
```

- **`CLAUDE.md` / `AGENTS.md` 建议**：一段可直接粘贴的 `agentops:repo-rules` 托管块（每条反复规则一行，各带 N/M 复现证据，加法），加上确定性精简诊断（减法：超出 ~200 行预算、逐字重复 README），文件缺失时再附「建议新建」。这套 `repo-rules` marker 刻意区别于 `init` 的 `session-protocol` marker，可在同一文件中共存。
- **hook 提案**：为每个达到复现阈值的失败模式给出一条 Claude Code hook（事件 + 现成的 `agentops` 命令）和可复制的 `settings.json` 片段；映射到同一命令的模式会合并为一条。
- **工作流指引**：一句趋势摘要 + 推荐的 `eval → memory → suggest` 运行节奏 + 从 skill 候选派生的 skill 脚手架。
- **建议而非改写**：`agentops suggest` 只在 `--output` 下写**评审草案**，对目标仓库的 `CLAUDE.md` / `AGENTS.md` / `README.md` 完全只读，从不就地修改；是否采纳由用户决定。
- 资产是记忆 + 指令文件的**可再生投影**：同样输入产出字节一致的资产，每次运行覆盖重写（绝不 append）。历史缺失或为空时同样以结构化错误退出（提示先跑 `agentops eval`）。

## 输出示例

AgentOps Harness 会将本地分析结果写入 `.agentops/`：

```text
.agentops/
  session-protocol.md      # init 写入的会话协议
  agentops-session.md      # Agent 按协议追加工作日志的位置
  agentops-report.md       # scan 输出的 readiness 报告
  agentops-score.json
  agentops-trace.json
```

`agentops scan` 生成的 `agentops-report.md` 是面向开发者的可读报告。每条扣分都附带证据和可执行建议，而不是一个空泛的分数：

```markdown
# AgentOps Repository Readiness Report

Score: 60/100

## Findings

- **missing_agent_instructions** (warning): Repository-specific agent
  instructions are missing. Evidence: `AGENTS.md`, `CLAUDE.md`
- **missing_ci_config** (warning): A common CI configuration was not
  detected. Evidence: `.github/workflows`, `.gitlab-ci.yml`

## Recommendations

- **Add agent instructions**: Add AGENTS.md or CLAUDE.md with boundaries
  and verification commands.
- **Add continuous integration checks**: Add CI configuration that runs
  the repository verification commands.
```

`agentops-trace.json` 记录扫描 workflow 的执行步骤和失败信息，便于定位问题。

`agentops eval` 向 `--output` 目录写入一组评测产物：

```text
<output>/
  agentops-report.md      # 评测报告：声明 vs 改动、发现、评分、建议、意图裁决
  agentops-score.json     # 结构化 EvalResult
  agentops-trace.json     # 评测 workflow trace
  eval-history.jsonl      # 每次评测追加一行（带时间戳），用于趋势分析
```

`agentops memory` 把上面累积的 `eval-history.jsonl` 投影为一组记忆产物（覆盖写出）：

```text
<output>/
  agentops-memory.md       # 人读记忆：趋势、失败模式（含 N/M + 热点路径）、规则候选、skill 候选
  agentops-memory.json     # 结构化 RepoMemory（供后续阶段/工具链消费）
  skill-candidates.md      # 聚焦、可评审的 skill 候选清单
  agentops-trace.json      # 记忆 workflow trace
```

`agentops suggest` 把累积记忆 + 现有指令文件投影为一组可采纳的改进资产（覆盖写出）：

```text
<output>/
  suggested-claude-md.md     # CLAUDE.md 的可采纳 repo-rules 块（加法）+ 精简诊断（减法）+ 缺失提示
  suggested-agents-md.md     # 同形，针对 AGENTS.md
  suggested-hooks.md         # 每个反复失败模式一条 hook 提案 + settings.json 片段 + 工作流指引 + skill 脚手架
  agentops-suggestions.json  # 结构化 ImprovementAssets（供 Studio / Phase 7 消费）
  agentops-trace.json        # suggest workflow trace
```

| 文件 | 用途 |
| --- | --- |
| `session-protocol.md` | Agent 记录工作日志的固定协议 |
| `agentops-session.md` | Agent 按协议追加的有界任务日志 |
| `agentops-report.md` | 面向开发者的仓库 readiness 或会话评测报告 |
| `agentops-score.json` | 面向工具链的结构化评分和诊断证据 |
| `agentops-trace.json` | 扫描 / 评测 / 记忆 workflow 的执行步骤和失败信息 |
| `eval-history.jsonl` | 每次评测追加一行的 append-only 历史，记忆的唯一数据来源 |
| `agentops-memory.md` | 仓库记忆报告：趋势、失败模式、规则候选、skill 候选 |
| `agentops-memory.json` | 结构化仓库记忆，供 Phase 6 / 工具链消费 |
| `skill-candidates.md` | 可以沉淀为 skill 的重复经验 |
| `suggested-claude-md.md` | `CLAUDE.md` 改进草案：可采纳 repo-rules 块（加法）+ 精简诊断（减法）+ 缺失提示 |
| `suggested-agents-md.md` | `AGENTS.md` 改进草案（同形） |
| `suggested-hooks.md` | hook 提案 + `settings.json` 片段 + 工作流指引 + skill 脚手架 |
| `agentops-suggestions.json` | 结构化 ImprovementAssets，供 Studio / Phase 7 消费 |

## 项目边界

AgentOps Harness 不实现另一个 coding agent，也不替代 Claude Code、Codex 或 Cursor。它为这些工具补充仓库级的质量评测、问题诊断和经验沉淀能力。

## 本地开发

安装开发依赖并运行测试套件：

```shell
python -m pip install -e ".[dev]"
python -m pytest
```

项目采用确定性规则优先、先写失败测试再实现的方式推进，开发约定见 `docs/`。

## 开发状态

项目仍在早期开发中，接口可能调整。当前已经打通仓库 readiness 扫描、仓库初始化、确定性 workflow 追踪，以及 scope 维度的会话评测（`agentops eval`，确定性评分 + `eval-history.jsonl` 数据累积），并支持可选的 LLM 意图裁决（`--intent-judge llm`，对每条漂移发现给出 `within_intent` / `drift`，任何失败都降级为确定性 `needs_review`，且不改变分数），仓库记忆的确定性投影（`agentops memory`，把累积历史蒸馏为趋势、失败模式、规则候选和 skill 候选，离线、可再生、不移动分数），以及把记忆 + 现有指令文件投影为可采纳改进资产的确定性生成（`agentops suggest`，产出 `CLAUDE.md` / `AGENTS.md` 托管块 + 精简诊断、hook 提案和工作流指引，对目标仓库只读、离线、可再生、不移动分数）；更多评测维度、问题诊断和实时旁路监督正在按阶段推进。欢迎提交 Issue 讨论真实 AI coding 工作流中的使用场景和需求。
