# AgentOps Harness

AgentOps Harness 是一个面向真实代码仓库的 AI coding 工作质量评测与优化系统。

Claude Code、Codex、Cursor 等工具可以执行开发任务。AgentOps Harness 关注这些工具在真实仓库中的工作质量：它观察工作过程，解释问题原因，并将一次开发中的经验沉淀为可复用的仓库资产。

它帮助你回答：

- 当前 Agent 是否读取了正确上下文。
- 修改是否超出任务边界。
- 验证证据是否充分。
- 长对话是否开始退化。
- 哪些规则应该写进 `CLAUDE.md` 或 `AGENTS.md`。
- 哪些重复经验应该提炼为 skill、hook、测试命令或工作流建议。

## 功能

- **仓库就绪度扫描**：识别项目结构、测试命令、CI 配置和 Agent 约束文件。
- **开发过程评测**：结合任务描述、会话记录、git diff、命令输出和测试结果，分析一次 AI coding 工作。
- **问题诊断**：识别上下文缺失、修改越界、验证不足、重复失败和任务膨胀。
- **改进建议**：给出 `CLAUDE.md`、`AGENTS.md`、skill、hook、验证命令和上下文管理建议。
- **经验沉淀**：积累仓库级失败模式和规则，让后续 AI coding 更稳定。

## 安装

要求 Python 3.11 或更高版本。

```shell
git clone https://github.com/muyuzhong/AgentOps.git
cd AgentOps
python -m pip install -e .
```

## 使用方式

项目处于早期开发阶段。目前可以检查 CLI：

```shell
agentops --help
agentops --version
```

仓库扫描、离线过程评测和改进建议功能正在开发中。后续版本将提供：

```shell
# 扫描仓库的 AI coding readiness
agentops scan --repo <repo-path>

# 评估一次 AI coding 工作过程
agentops eval \
  --repo <repo-path> \
  --transcript <session.md> \
  --diff <changes.diff>
```

## 输出示例

AgentOps Harness 会将本地分析结果写入 `.agentops/`：

```text
.agentops/
  agentops-report.md
  agentops-score.json
  suggested-claude-md.md
  suggested-agents-md.md
  skill-candidates.md
```

| 文件 | 用途 |
| --- | --- |
| `agentops-report.md` | 面向开发者的仓库 readiness 或会话评测报告 |
| `agentops-score.json` | 面向工具链的结构化评分和诊断证据 |
| `suggested-claude-md.md` | `CLAUDE.md` 改进草案 |
| `suggested-agents-md.md` | `AGENTS.md` 改进草案 |
| `skill-candidates.md` | 可以沉淀为 skill 的重复经验 |

## 项目边界

AgentOps Harness 不实现另一个 coding agent，也不替代 Claude Code、Codex 或 Cursor。它为这些工具补充仓库级的质量评测、问题诊断和经验沉淀能力。

## 开发状态

项目仍在开发中，接口可能调整。欢迎提交 Issue 讨论使用场景和需求。
