# Changelog

## [Unreleased] - 2026-09-05

- 方案 B：保留四级责任模式，按本次任务影响选择记录；精简 Skill 入口、按需建台账、明确接手阅读顺序与事实状态。
- 修复版本字段定位、暂存和清单修改保护；读取破坏性提交正文并使用已交付版本基线，风险不再强制 major。
- 用统一安装清单校验暂存包；历史发布报告不再是运行时依赖，适配器明确 Skill 安装位置。
- 校验状态结构、策略/Gate 与当前证据；新增 verify 命令绑定实际命令结果、任务和文件指纹。
- 迁移保留来源摘要，允许已确认保留副本重复检查；未知并存状态仍拒绝自动认领。
- 保留全部兼容模板与历史资料。未创建 GitHub Release、Tag 或执行远程写入。

本项目的所有重要变化都会记录在此文件中。

## [2.1] - 2026-08-30

- 新增 `workflow.py version-bump`（LEVEL 1/2）：自动探测版本源（`VERSION`/`package.json`/`pyproject.toml`/`Cargo.toml`），按版本 Tag 以来的提交分级（major/minor/patch），保持 X.Y 或 X.Y.Z 段数计算新版本；dry-run 展示计划，并入 GitHub 交付计划确认后 `--apply` 写回并创建 `chore(release): v<新版本>` 发布提交；目标项目已有 `CHANGELOG.md` 时自动插入版本条目；无版本文件时创建根 `VERSION` 初始 `0.1`；LEVEL 3 拒绝执行。
- 规则文档见新增 `references/release-versioning.md`；Git 动作矩阵新增"版本更新与交付提交"一行；`release-record.md` 模板新增"版本来源与分级依据"字段。
- 补齐过程文档：`docs/superpowers/plans/2026-08-30-flow-alignment.md`（回填本日流程对齐批次）与 `2026-08-30-release-versioning.md`（本功能执行计划）。
- LEVEL 2 初始化时检测到非 Git 仓库，先取得用户确认，再由新增的 `workflow.py git-init --confirm` 执行 `git init` 并只提交 `.elx-level/` 与 `docs/elx-level/` 工作流基线。
- LEVEL 1/2 每个切片验证全部通过后必须创建只包含当前任务的本地提交（当前分支含默认分支均可），未验证不提交；LEVEL 3 保持宿主仓库的分支与提交规则。
- LEVEL 2 新增 G2 Demo/原型环节与 `templates/level2/demo.md`：跨模块新功能在 G1 需求确认后、G3 技术方案前先做可运行验证；Gate 编号理顺为 G0 立项、G1 需求、G2 原型、G3 技术、G4 任务、G5 验收、G6 发布。
- LEVEL 4 新增节点 0 环境搭建（Git 仓库 + `AGENTS.md`），负责人确认实施后、进入后续节点前执行。
- LEVEL 1 Project Brief 定稿前 Agent 必须列出关键假设并逐项提问确认；「必做功能 + 范围冻结」明确为本级计划载体。
- 三个 LEVEL 新增"回到受影响阶段"回环规则：需求或方案被推翻时回到对应阶段重新确认，不带着已证伪的方向继续实现。
- 修复双语 README 契约：`README.en.md` 对齐重设计后的中文结构；安装脚本固定 UTF-8 输出编码，避免中文提示在重定向时乱码。

## [2.0] - 2026-08-20

- 产品与 Skill 正式更名为 ELX Level / `elx-level`，新安装目录统一使用 `elx-level`。
- 新项目状态迁移到 `.elx-level` 与 `docs/elx-level`，旧 `.project-workflow` 通过显式命令一次性复制并保留为回滚来源。
- 不提供长期可发现的旧 Skill 别名；`Project Level Workflow 1.0` 与 `v1.0` 保留为旧品牌最终稳定版本。
- LEVEL 1–4、`AUTO` / `CONFIRM` / `MANUAL_ONLY`、Schema `2.0` 和 GitHub 远程确认边界保持不变。

## [1.0] - 2026-08-16

- 公共版本改为两段式 `1.0`，状态 Schema 升级为 `2.0`，并兼容迁移 `0.4.0` 三段版本状态。
- LEVEL 1 改为快速开发与完整项目记忆，使用稳定认知层、演进记录层和轻量 Change/Progress Record。
- LEVEL 2 全量采用包内 PVS、Phase 0 → Phase N、范围冻结和 DoD；普通 Phase 完成不再形成审批 Gate。
- LEVEL 3 优先复用 Issue、PR、CHANGELOG、ADR 和仓库文档，不为小改动创建平行完整 PVS 文档树。
- LEVEL 4 改为先分析、负责人确认后可实施，保留十节点参考并只路由外部专业能力。
- LEVEL 1–3 对用户使用 `AUTO`、`CONFIRM`、`MANUAL_ONLY`；状态继续兼容内部 R1–R4。
- 所有 LEVEL 的 GitHub 远程交付自动路由 Codex GitHub 插件，执行前统一确认并在完成后回读验证。
- 新增双层文档、项目架构、Change Record、Release Record、个人执行循环和路由契约；旧模板继续作为兼容入口。

## [0.4.0] - 2026-08-16

- 将 Project Vibe Spec 治理内核、两份参考规则和完整 governance starter 嵌入 `core/project-vibe-spec/`，包内只保留根 `SKILL.md` 一个可发现入口。
- 以 `templates/template-map.json` 确立 PVS starter 为 LEVEL 2 重叠治理职责的唯一默认模板，同时保留原 `templates/level2/` 路径作为兼容入口。
- Doctor 与 `validate-package` 新增 PVS 内核完整性、模板映射、单 Skill 和无外部安装指令校验。
- PowerShell 与 POSIX 安装器增加包预检、PVS 文件统计、staging 替换、冲突备份和失败回滚；独立安装的 `project-vibe-spec` 只告警，绝不修改或删除。
- `status` 与 `transition` 在显式状态写入时安全刷新 `workflow_version`，保留旧状态备份和 `workflow_version_updated` 历史；只读 `validate` 保持字节级不变。
- Codex、Claude Code、Cursor 适配器统一引用包内 Bridge 与 PVS 内核，并新增单 Skill、离线和无需独立 PVS 的 eval 覆盖。

## [0.3.0] - 2026-08-13

- 将四级模型合并到根目录唯一权威文档 `LEVEL.md`，删除四份分散 SOP 和旧三级兼容入口。
- CLI、Doctor、包校验、状态摘要和三平台适配器统一引用 `LEVEL.md` 的当前等级章节。
- 安装、更新和卸载契约只管理统一 `LEVEL.md`，不再复制旧版 LEVEL 文件。
- 将持续运营所需的立项、PRD、技术、任务、发布和回滚模板从旧 LEVEL 3 归位到 LEVEL 2；LEVEL 3 只保留已有、团队与开源项目改进模板。
- 保留旧状态 `1→1、2→3、3→4` 的安全迁移能力，但不再保留冗余旧文档入口。

## [0.2.0] - 2026-08-12

- 将项目模型从三级调整为四级：快速验证、可持续运营、已有/开源改进和复杂项目需求分析。
- 明确“持续更新”与“持续运营”的区别，静态、离线和可下载更新物默认保留 LEVEL 1。
- 为 LEVEL 1/2 增加 PVS-Lite、完整 PVS 和待验证事项桥接说明。
- 将旧 LEVEL 2/3 的责任模式迁移到新 LEVEL 3/4，并保留旧文件名兼容入口。
- 增加旧状态 `1→1、2→3、3→4` 迁移、备份、STATUS 记录和迁移后人工 Gate；支持显式重确认旧 LEVEL 3 为新 LEVEL 2。
- 更新四级状态校验、Doctor、包校验、适配器、模板、安装器、更新器、评测和测试。

## [0.1.0] - 2026-08-07

- 建立三级项目开发流程 Skill 首版。
- 规划 Codex、Claude Code 和 Cursor 共享核心与平台适配器。
- 定义低风险自动推进、人工 Gate、状态恢复和 Git/Draft PR 权限边界。
- 提供 Codex、Claude Code、Cursor 三平台适配器和跨平台生命周期脚本。
- 增加状态 CLI、Git 动作策略、中文场景 Evals 与发布前全包校验。
