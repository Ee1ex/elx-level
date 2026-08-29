---
name: elx-level
description: 当用户要开发个人项目、持续运营产品、改进已有或开源仓库、分析复杂自动化需求、判断 LEVEL，或按可恢复流程推进到交付时使用。支持 LEVEL 1–4、双层项目记忆、低重复审批和外部能力路由。
compatibility: Codex、Claude Code、Cursor；核心脚本需要 Python 3.10+，安装器支持 PowerShell 或 POSIX Shell。
---

# ELX Level

ELX Level 把项目推进变成可恢复、可验证、个人开发优先的流程。LEVEL 表示责任模式；LEVEL 1–3 对用户只展示 `AUTO`、`CONFIRM`、`MANUAL_ONLY`，R1–R4 仅作为兼容状态和内部依据。

## 触发检查

在执行前确认用户确实要求推进项目、初始化流程或判断等级。

应使用本 Skill：

- 开发小工具、插件、网页、游戏 Mod、App、SaaS、小程序或客户端。
- 修改已有项目、团队仓库或 GitHub 开源项目。
- 建设需要上线并持续运营的自有产品或在线服务。
- 分析大型产品、多系统自动化或复杂编排的需求。
- 判断项目应采用哪个 LEVEL，或继续到下一个人工 Gate。
- 用户明确指定 LEVEL 1、LEVEL 2、LEVEL 3 或 LEVEL 4。

不要使用本 Skill：

- 只问知识、解释代码、只读 Review 或纯诊断且没有修改授权。
- 明确要求创建、修改或调试 Agent Skill；此时优先使用专门的 Skill 创建流程。

如果请求同时包含诊断和修复，先完成诊断并确认根因，再进入本流程。

## 第一步：发现项目与状态

1. 确定项目根目录，不对不明确的路径执行写操作。
2. 从根目录向上读取适用的 `AGENTS.md`、`CLAUDE.md`、`.cursor/rules/`、`CONTRIBUTING.md`、README 和项目文档。
3. 检查 `.elx-level/state.json`；存在时先运行 `python scripts/workflow.py validate --project <项目根目录>`。只有旧 `.project-workflow` 时提示运行 `migrate`，不得隐式复制。
4. 验证通过后读取 `docs/elx-level/STATUS.md` 和当前任务；状态与聊天、代码或项目规则冲突时展示差异并询问。
5. 状态不存在时进入 LEVEL 推荐，不直接创建大量文档或修改实现。

状态协议见 `references/state-protocol.md`；双层文档见 `references/documentation-contract.md`；个人连续执行见 `references/personal-execution-loop.md`；PVS 分层见 `references/project-vibe-spec-bridge.md`；LEVEL 4 能力路由见 `references/level4-capability-routing.md`；GitHub 交付见 `references/github-plugin-routing.md`；通用工具路由见 `references/tool-routing.md`。

包内 PVS 治理入口为 `core/project-vibe-spec/PVS.md`。按 Bridge 只加载当前 LEVEL 需要的章节和模板；不得要求用户另行安装、查找或下载 `project-vibe-spec`。包内入口缺失时按包损坏停止，不回退到个人 Skills 目录中的独立副本。

## 第二步：推荐并确认 LEVEL

按 `references/level-selection.md` 判断责任模式，不以代码行数或“以后可能更新”为唯一依据。选择顺序：

1. 他人、团队、公司或开源仓库的参与/改进 → LEVEL 3。
2. 自有、线上、需要持续运营并承担用户/数据/服务责任 → LEVEL 2。
3. 离线、静态或可下载交付，重新打包即可更新 → LEVEL 1。
4. 大型、多系统、复杂自动化或完整运营自动化 → LEVEL 4，先分析，负责人确认后可实施。

输出：

- 推荐 LEVEL。
- 已确认事实与仍属假设的内容。
- 推荐理由，尤其是持续更新与持续运营的区别。
- 改用其他 LEVEL 会省略或增加什么。
- 需要项目负责人确认的问题。

用户明确确认前，不初始化正式流程、不写代码、不创建数据库、不部署、不创建远程资源。确认后读取根目录唯一权威文档 `LEVEL.md` 中当前等级的章节，不加载或维护分散的 LEVEL SOP。

## 第三步：初始化最小项目文档

运行：

```text
python scripts/workflow.py init --project <项目根目录> --level <1|2|3|4>
```

`init` 只写入 `.elx-level/state.json`、`state.backup.json` 和 `docs/elx-level/STATUS.md`，不未经确认生成大量项目文档。

LEVEL 2 项目根目录还不是 Git 仓库时，先向用户说明并取得确认；确认后运行：

```text
python scripts/workflow.py git-init --project <项目根目录> --confirm
```

它执行 `git init` 并只暂存 `.elx-level/` 与 `docs/elx-level/` 创建基线提交；目录已是 Git 仓库时拒绝执行。LEVEL 1、3、4 不自动初始化 Git，需要时按 `references/git-and-draft-pr.md` 的人工 Gate 处理。

- LEVEL 1：规则、文档地图、Project Brief、架构、Requirements/Decisions/Progress Ledger、轻量 Change Record、状态和待验证记录。
- LEVEL 2：完整 PVS 的 AGENTS、DOCUMENT_MAP、PDD/PRD、Requirements、Decisions、Progress、业务流、UI、架构、API、数据、权限、部署、监控、备份、回滚、运营、Bug 和版本记录。
- LEVEL 3：优先复用 Issue、PR、CHANGELOG、ADR 和仓库文档，只补项目地图、Change Record、受影响基线、回归、PR 和交接。
- LEVEL 4：先建立需求分析和方案，负责人确认实现后按十节点参考和外部能力路由推进。

模板位于 `templates/`；已有项目目录和事实文档优先，不能创建平行事实源。

## 第四步：选择执行策略与硬边界

读取 `references/personal-execution-loop.md` 和 `references/risk-and-permissions.md`，记录目标、范围、不做、允许/禁止修改、验收标准、验证命令和执行策略。未运行的检查写入待验证记录，不得标记为通过。

- `AUTO`：已确认范围内连续执行。
- `CONFIRM`：缺少用户决策或即将产生高影响。
- `MANUAL_ONLY`：Agent 只准备，不执行。

内部 R1–R4 为旧状态兼容保留，不要求 LEVEL 1–3 普通任务逐轮展示：

- R1：文档、模板、只读分析、独立小测试；可执行并留证据。
- R2：边界清晰的逻辑和内部 API；批准范围内执行，必须测试与 Review。
- R3：数据库、认证、权限、公共 API、部署配置；修改前和合并前人工批准。
- R4：生产数据、密钥、支付、不可逆迁移、生产发布；只分析和准备，不自主执行。

## 各 LEVEL 的实现边界

### LEVEL 1：快速开发与完整项目记忆

按 Bridge 使用 PVS 可追溯核心和双层文档，以“实现—运行—观察—调整”为主。小变更追加 Progress/Changelog，小功能和 Bug 使用 Change Record，跨模块变更使用 REQ + PROG 并同步架构事实。完成或打包前集中验收；删除数据、密钥和外部写入仍按硬边界确认。

### LEVEL 2：完整 PVS 持续运营

读取 `core/project-vibe-spec/PVS.md` 全部流程及其两份 reference，使用 Phase 0 → Phase N、范围冻结和 DoD 推进。跨模块新功能在需求确认后、技术方案前，用 `templates/level2/demo.md` 完成 Demo/原型验证（G2）。普通 Phase 完成后自动继续，不形成用户 Gate；方向、架构、数据、权限、安全、兼容、生产和 Release 变化时切换为 `CONFIRM`。

### LEVEL 3：已有与开源项目改进

按 Bridge 读取包内 PVS 的事实确认、跨模块影响、验证与 Git 交付原则，保留原有仓库的项目地图、权限与贡献规则、修改前基线、问题复现、失败测试/人工复现、影响分析、受影响回归、CI、Review、PR、发布和交接责任。改动小不等于可以跳过基线与回归。

### LEVEL 4：复杂自动化参考与路由

按 Bridge 先完成需求、范围、MVP、方案和风险分析；负责人通过 `level4-execution-review` 后可实施，先完成节点 0 环境搭建（Git 仓库与 `AGENTS.md`）再进入后续节点。需求、原型、技术方案、任务拆解、实现、测试、Review、部署准备、日志和复盘所需专业 Skill 只路由、不得内嵌；缺失时说明来源、用途、权限和降级方案，安装前提醒用户确认。

## 状态迁移

`migrate` 可把旧 `.project-workflow` 一次性复制到 `.elx-level`，旧目录保持不变；新旧目录并存时停止且不覆盖。`0.4.0` 状态迁移到 `2.0` 时 LEVEL 1–4 保持不变；LEVEL 4 保持分析阶段并进入 `level4-execution-review`。更老 Schema 的历史数字映射继续兼容。迁移前写 `state.backup.json` 并记录旧/新版本、等级和原因。

## 连续执行与人工 Gate

读取相关实现、测试、配置和文档，建立修改前基线；一次完成一个最小可验证切片；运行必要检查；检查 Diff；同步稳定认知与演进记录。普通进度、测试通过、功能完成和本地提交不是 Gate。出现实质范围、方向、架构、数据、权限、安全、兼容、生产、公开发布、外部 Provider 或高影响 Git 变化时切换为 `CONFIRM` 或 `MANUAL_ONLY`。

Git 默认不执行远程写入；`allow_push_own_branch=false`、`allow_create_draft_pr=false`，两个字段只保留范围配置。LEVEL 1/2 的每个切片在验证全部通过后必须创建只包含当前任务的本地提交（当前分支含默认分支均可），未验证不提交；LEVEL 3 沿用宿主仓库的提交规则。所有 LEVEL 的 push、Draft PR、Merge、Tag 和 Release 自动选择 Codex GitHub 插件，先形成合并计划并在执行前确认，完成后回读验证。Force Push 和改写公共历史永久禁止。Qima 只在能力缺口明确时提醒用户手动考虑，不得直接调用或自动串联。

## 平台适配

读取 `references/platform-compatibility.md`。Codex、Claude Code 和 Cursor 只处理路径、发现和格式差异，均引用 `LEVEL.md` 的当前等级章节，不重写等级流程。

## 每轮输出

报告当前 LEVEL、阶段、执行策略、本轮改动和原因、实际运行的命令及结果、本地 Git 状态、未执行检查、下一步和是否需要确认。LEVEL 1–3 不为普通任务重复展示空风险或空 Gate；没有新鲜验证证据时，不声称任务完成。
