# AgentOps Harness 文档索引

本文档目录服务于项目设计和开发协作。GitHub 用户只需要阅读仓库根目录的 `README.md`。

## 必读文档

| 文档 | 用途 |
| --- | --- |
| `../agent.md` | AI coding agent 的任务入口和固定工作协议 |
| `project-memory.md` | 跨会话项目记忆：当前状态、已完成能力、已知限制和下一步 |
| `positioning-and-boundaries.md` | 项目定位、边界、最终形态 |
| `architecture.md` | 通用架构、模块职责、数据流和架构约束 |
| `development-roadmap.md` | 开发顺序、并行边界和 git worktree 协作规则 |

## 实施计划

`superpowers/plans/` 保存可执行的功能计划。每份计划只覆盖一个可独立验收的纵向切片。

当前计划：

| 计划 | 状态 |
| --- | --- |
| `superpowers/plans/2026-05-30-phase-0-core-scaffold.md` | 已完成 |
| `superpowers/plans/2026-05-30-phase-1-minimal-repo-scan.md` | 已完成 |

## 文档职责

- `README.md` 面向 GitHub 用户，不承载内部开发细节。
- `agent.md` 面向参与开发的 AI coding agent，只保留进入任务前必须知道的规则。
- `project-memory.md` 记录会随开发变化的事实。
- `positioning-and-boundaries.md` 和 `architecture.md` 记录相对稳定的设计决策。
- `development-roadmap.md` 记录开发顺序和并行协作方式。
- `superpowers/plans/` 保存逐任务实施步骤。
