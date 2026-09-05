# 平台兼容协议

## 何时读取

安装 Skill、生成项目规则、切换 Agent、渲染适配器、执行状态迁移或诊断平台触发问题时读取。

## 共享核心

三个平台共同读取根目录 `SKILL.md`、唯一权威 `LEVEL.md`、`references/`、`templates/`、`core/project-vibe-spec/PVS.md` 和项目状态。平台适配器不得复制或改写业务流程，只显示当前 LEVEL、`LEVEL.md` 对应章节、包内 PVS 分层边界和状态路径。任何平台都不要求用户另装第二个 PVS Skill。

## Codex

- 个人 Skill 安装到 Codex Skills 目录，项目也可保留仓库内共享副本。
- 项目规则使用根目录 `AGENTS.md`。
- 适配器渲染 `AGENTS.md` 的托管区块，保留用户区块。

## Claude Code

- 使用个人或项目 `.claude/skills/<skill-name>/SKILL.md`。
- 项目持久规则使用 `CLAUDE.md`，只放项目事实、命令和边界。
- 适配器渲染 `CLAUDE.md` 的托管区块，保留用户区块。

## Cursor

- 使用 `.cursor/rules/elx-level.mdc` 项目规则。
- 可同时使用简洁 `AGENTS.md` 作为通用项目入口。
- 不生成旧式 `.cursorrules`。
- 规则引用共享 `LEVEL.md`、状态和当前任务，不复制完整流程。

## 四级适配策略

- LEVEL 1 显示 PVS-Lite 和集中冒烟/打包验证边界。
- LEVEL 2 显示完整 PVS、持续运营和风险/里程碑验证边界。
- LEVEL 3 显示已有仓库基线、回归、Review、PR 和交接责任。
- LEVEL 4 显示先分析、负责人确认后可实施，并按需路由外部专业能力。

## 状态迁移

适配器读取迁移后的状态，不自行推断旧数字含义。Schema 1.1.0 保持 LEVEL 数字；更老状态按 1→1、2→3、3→4 映射并进入 level-migration-review。显式改新 LEVEL 2 需批准记录；具体以 state-protocol.md 为准。

## 降级

平台不支持自动 Skill 发现时，用户显式引用项目规则或 `SKILL.md`。平台没有某个 Plugin 时走通用流程。任何平台都不能把指令文件视为操作系统级权限边界。

## 安装与项目路径

适配器显式标出 Skill 包位置。项目内安装使用相对项目根目录的路径，可随整个项目移动；用户级安装使用本机位置，换主机后重新运行 render-adapter。所有命令从项目根目录执行，不能把宿主 scripts/workflow.py 当作本 Skill 脚本。安装清单唯一来源为 package-files.json，替换前校验暂存包；历史 docs 不属于运行时依赖。
