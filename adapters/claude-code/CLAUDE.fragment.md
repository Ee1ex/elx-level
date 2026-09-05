<!-- elx-level:start -->
## ELX Level 托管入口

- 当前流程：LEVEL {{LEVEL}}
- 权威等级流程：`{{LEVEL_DOC}}`
- 当前分层策略：{{LEVEL_MODE}}
- Skill 包位置：`{{PACKAGE_ROOT}}`；用户级安装换主机后重新渲染入口。
- 机器状态：`.elx-level/state.json`
- 人类摘要：`docs/elx-level/STATUS.md`
- 状态校验：`python "{{PACKAGE_ROOT}}/scripts/workflow.py" validate --project .`
- PVS 分层路由：`{{PACKAGE_ROOT}}/references/project-vibe-spec-bridge.md`
- PVS 包内内核：`{{PACKAGE_ROOT}}/core/project-vibe-spec/PVS.md`
- 双层文档契约：`{{PACKAGE_ROOT}}/references/documentation-contract.md`
- 外部能力边界：LEVEL 4 专业能力只路由、不内嵌，安装仍需确认

恢复会话时先校验状态。按 `LEVEL.md` 对应章节和当前执行策略推进，保留用户已有修改；到人工 Gate 后报告事实、证据、方案和推荐决策。LEVEL 4 先分析，负责人确认后可实施并路由外部能力。
<!-- elx-level:end -->
