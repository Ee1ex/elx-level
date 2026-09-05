# ELX Level 的 Project Vibe Spec 包内分层桥接

本文件说明 ELX Level 如何按 `LEVEL.md` 加载包内 `core/project-vibe-spec/PVS.md`。`LEVEL.md` 始终是唯一的 LEVEL 权威；本桥接只规定 PVS 的加载深度和边界，不重新定义等级。

运行时不安装、不下载、不查找、也不回退到外部 `project-vibe-spec` Skill。项目已有规则和事实文档优先，包内模板只补齐缺失职责；独立安装的同名 Skill 不属于本包托管范围。

## 加载矩阵

| LEVEL | PVS 范围 | 模板职责 | 边界 |
| --- | --- | --- | --- |
| 1 | 可追溯核心、稳定认知、演进记录 | PVS Ledger + LEVEL 1 记忆模板 | 不为小切片铺大型方案 |
| 2 | 完整 PVS、两份 references 与 governance starter | `templates/template-map.json` | Phase 完成不自动形成审批 Gate |
| 3 | 事实、跨模块、验证、Git | 既有仓库文档为主，PVS 补缺 | 不强制铺设完整治理包 |
| 4 | 需求、方案、数据 Gate、风险与参考节点 | 分析记录 + 外部能力路由 | 实现前经负责人确认 |

## LEVEL 1：可追溯核心与完整记忆

LEVEL 1 使用 PVS 可追溯核心支持快速开发，同时保留完整项目记忆。按需覆盖以下职责，可合并文档、不创建空台账：

- 读取项目规则和已有 README/文档，不能跳过 `AGENTS.md` 等约定。
- 根目录 `AGENTS.md`：行为规则、文档优先级和入口索引。
- 根目录 `DOCUMENT_MAP.md`：真实文档路径索引，不承载业务事实。
- Project Brief、架构和模块事实：目标、范围冻结、核心路径、调用、数据、构建与交付。
- 一处轻量 Change/Progress Record；首次需要时再建 Requirements、Decisions、Progress Ledger。
- `docs/elx-level/STATUS.md`、`.elx-level/state.json` 和状态备份。
- 必要的决策和待验证事项；未运行的检查只能记录为待验证。

小变化不需要逐条详细 REQ 或全套 PDD/PRD；跨模块功能使用 REQ + PROG，有取舍时增加 DEC。开发以“实现—运行—观察—调整”为主，完成或打包前集中做核心路径冒烟、构建/打包和人工验收。

## LEVEL 2：完整 PVS

按受影响职责加载包内 `core/project-vibe-spec/PVS.md`、两份 references 和 governance starter，执行接管、需求、设计、数据、决策、进度、验证和交付流程：

- 复用或维护 `AGENTS.md`、`DOCUMENT_MAP.md` 和已有事实文档。
- 维护 PDD/PRD、Requirements/LEDGER.md、详细 REQ、决策记录和进度记录。
- 维护业务流、UI/交互规范、技术方案、API Contract、数据模型、权限、失败路径、部署、环境、日志、指标、监控、发布、回滚和运营说明。
- 实现过程中同步维护需求、决策、进度、状态和验证证据，保证换 Agent、换主机或开源交接后可快速建立认知。
- 使用 Phase 0 → Phase N、范围冻结和 DoD；Phase 达成后自动进入下一阶段，不自动索要人工批准。

完整 PVS 不等于每个小改动都运行重型测试。必要的快速检查保留，系统测试、回归、发布前验收按风险、功能集成、里程碑和版本完成阶段集中安排。认证、权限、支付、生产数据、迁移、密钥和生产发布必须事前做针对性验证并经人工 Gate。

## LEVEL 3：已有/开源项目改进

LEVEL 3 优先复用 Issue、PR、CHANGELOG、ADR 和仓库文档，保留轻量项目地图、Change Record、受影响基线、回归、PR 和交接。小改动不创建平行完整 PVS 文档树；跨模块变更必须同步架构或接口事实。

## LEVEL 4：分析、确认与外部路由

LEVEL 4 先建立机会/问题、目标用户、范围、不做、MVP、验收、方案和风险记录，负责人确认后可实施。实施参考需求、原型、技术方案、任务拆解、实现、测试、Review、部署准备、日志和复盘十节点；专业 Skill 只路由，不内嵌。负责人确认前不创建实现或远程资源，确认后仍遵守数据、权限、生产和发布 Gate。

## 文档复用原则

`DOCUMENT_MAP.md` 只负责导航，不替代需求、产品、技术、数据或运营事实。已有等价目录优先复用；不得为了套模板复制一套平行 `docs/`、`Requirements/` 或 `Progress/`。跨模块需求、持久化变化、公共 API、权限、安全、平台或部署变化需要详细需求、决策和行为验收记录。

## 验证分层

| 等级 | 最小验证 | 延后验证记录 |
| --- | --- | --- |
| 1 | 核心路径冒烟、构建/打包、必要人工验收 | `pending-verification.md`、STATUS 和交付记录 |
| 2 | 风险检查、功能集成、里程碑/版本测试、发布 readiness 和人工 Gate | 待验证、回滚、备份和运营责任记录 |
| 3 | 修改前基线、问题复现、失败测试/人工复现、受影响回归、CI、Review 和 PR | 交接、发布和维护者后续检查 |
| 4 | 需求验收标准、方案比较、风险和待确认事项 | 后续完整流程的前置条件 |

包内 `core/project-vibe-spec/PVS.md` 是本工作流使用的 PVS 治理依据；本桥接文档只定义它在四级模型中的加载深度和边界。
