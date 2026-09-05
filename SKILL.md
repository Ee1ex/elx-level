---
name: elx-level
description: 按项目责任与本次任务影响组织开发、维护和复杂自动化，保存可接手的项目事实、变更原因与验证证据。用于判断 LEVEL、初始化项目流程或继续实施；不接管纯解释、只读审查及 Agent Skill 的创建调试。
metadata:
  compatibility: Codex、Claude Code、Cursor；核心脚本需要 Python 3.10+，安装器支持 PowerShell 或 POSIX Shell。
---

# ELX Level

LEVEL 表示项目责任模式，不等于本次任务的工作量。保留 LEVEL 1–4，按任务影响选择文档和验证深度；普通进展使用 `AUTO`，实质决策使用 `CONFIRM`，仅人工操作使用 `MANUAL_ONLY`。

## 触发与接手

用户确实要求实施、初始化或判断等级时使用。纯解释、只读 Review、诊断且没有修改授权时不启动流程；明确创建、修改或调试 Agent Skill 时使用专门的 Skill 创建流程。诊断与修复同时出现时先确认根因。

1. 确认项目根目录和当前 checkout，读取适用项目规则。保留用户已有修改。
2. 接手顺序：规则 → 文档地图（或等价索引）→ `docs/elx-level/STATUS.md` → 当前任务 → 受影响实现及验证入口。只按链接加载相关事实，历史计划按需读取。
3. 存在 `.elx-level/state.json` 时先校验。只有旧 `.project-workflow` 时显式迁移，不隐式复制；新旧并存按迁移来源记录识别，未确认冲突时停止。
4. 区分当前已验证事实、批准但未实现的目标与假设。文档不代替代码检查；冲突影响范围或决策时展示证据并询问。

状态命令和恢复规则见 `references/state-protocol.md`。命令中的 `<Skill包目录>` 是当前已加载本 Skill 的实际目录，不能当作目标项目目录。

## 选择责任模式与任务粒度

等级选择只以根目录 `LEVEL.md` 的选择表为权威，边界案例见 `references/level-selection.md`。输出推荐、事实、假设和改用其他 LEVEL 的影响。用户明确确认前不初始化正式流程；已有有界授权持续有效，不重复审批同一决定。

确认后只读取 `LEVEL.md` 当前等级章节，以及 `references/documentation-contract.md` 的任务粒度表：

- 文案、样式、小配置：一条结构化变更记录。
- 局部功能或 Bug：一份 Change/Bug Record。
- 跨模块、多阶段：REQ + PROG；实质取舍增加 DEC。
- 架构、数据、权限、兼容变化：受影响事实、方案确认和针对性验证。

等级不会强制把每次小修改扩大为完整立项。已有等价事实源优先，空台账按需创建，不建立平行文档树。

## 初始化与执行

```text
python "<Skill包目录>/scripts/workflow.py" init --project <项目根目录> --level <1|2|3|4>
```

初始化只创建状态、备份和 STATUS；文档职责按需补齐。Git 初始化另经确认；已有 Git 项目按仓库规则提交。非 Git 的 LEVEL 1 可先用变更记录保留验证，不为留痕强制初始化 Git。

按 `references/personal-execution-loop.md` 实现最小可验证切片、检查行为与 Diff、同步当前事实和演进记录。只在范围、方向、数据语义、权限、安全、兼容或外部动作边界变化时重新确认。低影响任务不机械要求先写失败测试。

包内治理入口为 `core/project-vibe-spec/PVS.md`；按 `references/project-vibe-spec-bridge.md` 加载所需章节与模板，不要求外部 PVS 安装。包内入口缺失按包损坏处理。

## 验证、权限与交付

- 具体权限只以 `references/risk-and-permissions.md` 为准；R1–R4 保留为兼容与内部风险依据，不能代替用户授权。
- 验证记录必须关联当前任务和文件指纹；使用 `workflow.py verify` 执行实际命令。旧记录保留历史价值，不能自动批准当前代码。未执行检查明确留待验证。
- Git 规则见 `references/git-and-draft-pr.md`。默认 `allow_push_own_branch=false`、`allow_create_draft_pr=false`；配置不是远程动作批准。
- GitHub 插件或已声明替代工具的远程交付见 `references/github-plugin-routing.md`，先展示具体计划、执行前确认、完成后回读。Force Push 和改写公共历史禁止。
- 版本更新见 `references/release-versioning.md`，不强制创建 Tag 或 GitHub Release，宿主仓库规则优先。
- 通用能力选择见 `references/tool-routing.md`；LEVEL 4 见 `references/level4-capability-routing.md`，专业能力只路由，不内嵌。Qima 只在确有缺口时提醒，不得直接调用或自动串联。
- 平台入口与安装位置见 `references/platform-compatibility.md`。

## 交接输出

报告实际结果、关键变更及原因、验证结果、未验证项、当前任务记录和下一步。普通任务不重复输出空 Gate 或空风险；不把模板齐全或脚本退出 0 当作用户行为已验证。
