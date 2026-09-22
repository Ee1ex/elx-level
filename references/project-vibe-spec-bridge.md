# ELX Level 的 Project Vibe Spec 包内分层桥接

本文件说明 ELX Level 如何按 `LEVEL.md` 加载包内 `core/project-vibe-spec/PVS.md`。`LEVEL.md` 始终是唯一的 LEVEL 权威；本桥接只规定 PVS 的加载深度和边界，不重新定义等级。

运行时不安装、不下载、不查找、也不回退到外部 `project-vibe-spec` Skill。项目已有规则和事实文档优先，包内模板只补齐缺失职责；独立安装的同名 Skill 不属于本包托管范围。

## 加载矩阵

| LEVEL | PVS 范围 | 模板职责 | 边界 |
| --- | --- | --- | --- |
| 1 | 可追溯核心、稳定认知、演进记录 | PVS Ledger + LEVEL 1 记忆模板 | 不为小切片铺大型方案 |
| 2 | 完整治理职责，按下表读取受影响章节 | `templates/template-map.json` 中所需模板 | 小任务不重走立项；Phase 完成不自动形成审批 Gate |
| 3 | 事实、跨模块、验证、Git | 既有仓库文档为主，PVS 补缺 | 不强制铺设完整治理包 |
| 4 | 需求、方案、数据 Gate、风险与参考节点 | 分析记录 + 外部能力路由 | 实现前经负责人确认 |

## 按任务加载（所有 LEVEL）

遵守项目规则与主包权限协议，先读 `references/documentation-contract.md` 与 `references/personal-execution-loop.md`。以下 PVS 章节均位于 `core/project-vibe-spec/PVS.md`，按标题定位；同会话已读且未变化的规则沿用。

| 触发条件 | 增量读取 |
| --- | --- |
| 已接入项目的文案、样式、局部 Bug/功能，职责和边界清楚 | 主包契约、当前 LEVEL 和执行循环足够；不加载 PVS 全文、两份 reference 或 starter |
| 首次接入或缺少治理入口 | PVS §1；只检查适用职责，缺模板时再查 template-map 并打开所需模板 |
| 真实跨模块或多阶段任务 | PVS §2、§4、§5、§7；事实同步范围不清楚时读 §6 与 document-maintenance |
| 持久化、数据库、迁移或数据语义变化 | PVS §3、§7 与 references/decision-gates.md；先确认方案，保留失败/恢复验证 |
| 权限、安全、公共接口、核心依赖或外部服务变化 | 主包 risk-and-permissions + PVS §2、§7 与 references/decision-gates.md；必要时叠加数据规则 |
| 文档职责/路径变化或同步边界不清楚 | PVS §6 与 references/document-maintenance.md 的相关段落 |
| 版本或生产交付 | PVS §7、主包 Git/发布规则及当前项目部署、监控、备份/恢复事实 |

PVS 的 reference 路径相对 `core/project-vibe-spec/`。多个条件同时命中取并集；“小任务”不得覆盖数据、权限、生产和宿主仓库要求。模板只在缺少对应记录时打开；跨会话本身不触发完整加载。

## 各级责任仍按 LEVEL.md 执行

- LEVEL 1 保留双层记忆与一处演进记录，完成/打包前集中验证核心路径和交付物。
- LEVEL 2 完整承担适用产品、数据、权限和运营责任，不等于每轮全量读取或更新。按 Phase 0 → Phase N、范围冻结和 DoD 推进，普通阶段自动继续；保留功能集成、里程碑/版本验收及监控、备份、恢复责任。
- LEVEL 3 复用宿主文档与贡献流程，保留修改前基线、复现、受影响回归、CI、Review 和交接。
- LEVEL 4 先分析，负责人确认后可实施；专业 Skill 只路由、不内嵌，批准后仍遵守数据、权限、生产和发布 Gate。

地图只导航，已有事实源优先；具体建档与同步粒度统一见 documentation-contract，不在本文件重复定义。未运行的平台、兼容性或发布检查保留待验证，不能用减少读取代替验证。
