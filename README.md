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

- **仓库就绪度扫描**：识别项目结构、测试命令、CI 配置和 Agent 约束文件，输出 readiness 评分和可执行建议。
- **仓库初始化**：安装会话协议，向 `CLAUDE.md` / `AGENTS.md` 写入托管指令块，约定 Agent 如何记录工作日志。
- **工作流追踪**：记录确定性的扫描步骤和失败信息，便于检查执行过程。

开发中：

- **开发过程评测**：结合任务描述、有界任务日志、git diff、命令输出和测试结果，对账声明与真相，评估一次 AI coding 工作。
- **问题诊断**：识别上下文缺失、修改越界、验证不足、重复失败和任务膨胀。
- **仓库级改进建议**：给出 `CLAUDE.md`、`AGENTS.md`、skill、hook、验证命令和上下文管理建议。

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

### 评测一次工作过程（开发中）

离线过程评测和进一步的改进建议仍在开发中。后续版本将提供：

```shell
agentops eval \
  --repo <repo-path> \
  --transcript <session.md> \
  --diff <changes.diff>
```

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

后续版本还会逐步增加：

```text
  suggested-claude-md.md
  suggested-agents-md.md
  skill-candidates.md
  eval-history.jsonl
```

| 文件 | 用途 |
| --- | --- |
| `session-protocol.md` | Agent 记录工作日志的固定协议 |
| `agentops-session.md` | Agent 按协议追加的有界任务日志 |
| `agentops-report.md` | 面向开发者的仓库 readiness 或会话评测报告 |
| `agentops-score.json` | 面向工具链的结构化评分和诊断证据 |
| `agentops-trace.json` | 扫描 workflow 的执行步骤和失败信息 |
| `suggested-claude-md.md` | `CLAUDE.md` 改进草案 |
| `suggested-agents-md.md` | `AGENTS.md` 改进草案 |
| `skill-candidates.md` | 可以沉淀为 skill 的重复经验 |

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

项目仍在早期开发中，接口可能调整。当前已经打通仓库 readiness 扫描、仓库初始化和确定性 workflow 追踪；离线会话评测、问题诊断和改进资产生成正在按阶段推进。欢迎提交 Issue 讨论真实 AI coding 工作流中的使用场景和需求。
