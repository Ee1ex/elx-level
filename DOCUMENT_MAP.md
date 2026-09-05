# ELX Level 当前文档地图

当前版本交付状态见 [2.2 交付记录](docs/release/2.2-readiness.md)，推送说明见 [提交正文](docs/release/2.2-push-description.md)。

## 接手顺序

先读 AGENTS.md，再读本索引；当前方案 B 的结果和待验证项位于 docs/plan-b-results.md。实现从 scripts/workflow.py、package-files.json 和 tests/test_reliability_regressions.py 进入。

| 职责 | 当前来源 | 何时更新 |
| --- | --- | --- |
| Skill 入口与分层加载 | SKILL.md | 触发、路由与接手步骤变化 |
| 四级责任模型 | LEVEL.md | 项目责任模式变化 |
| 文档与任务粒度 | references/documentation-contract.md | 记录规则变化 |
| 状态与当前证据 | references/state-protocol.md、schemas/workflow-state.schema.json | 状态兼容或验证格式变化 |
| 权限与 Git | references/risk-and-permissions.md、references/git-and-draft-pr.md | 动作边界变化 |
| 模板映射 | templates/template-map.json | 默认职责、兼容入口变化 |
| 安装闭包 | package-files.json | 运行时资源增减 |
| 当前变更计划 | docs/superpowers/plans/2026-09-05-plan-b.md | 范围与验收变化 |
| 当前结果与验证 | docs/plan-b-results.md | 验证、限制和下一步变化 |
| 历史证据 | docs/superpowers/、docs/release/、CHANGELOG.md | 仅在回溯原因时读取 |

历史方案保留当时结论，不作为当前执行指令；不删除旧资料，不要求初次接手读取全部历史。
