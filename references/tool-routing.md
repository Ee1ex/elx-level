# 工具路由协议

## 何时读取

当前阶段需要产品设计、数据库、代码托管、部署、宣传或其他外部能力时读取。

## 通用规则

- 先判断能力缺口，再选工具；不要为了使用 Plugin 改变技术栈。
- 使用前检查安装、登录、授权、目标环境、费用、数据去向和退出方式。
- 外部写入、生产操作、数据库变更和公开发布遵守风险与人工 Gate。
- 工具不可用时使用通用文档、CLI 或人工流程，并记录未执行项。
- LEVEL 4 十节点使用 `references/level4-capability-routing.md`：外部专业能力只路由、不内嵌。

## 产品与设计

- Product Design：有真实流程、URL、截图、草图或视觉目标时使用研究、审计、方案探索和 Design QA。
- `frontend-design`、`ui-ux-pro-max`、`make-interfaces-feel-better`：视觉方向获批后用于实现与打磨。
- Qima：只提醒用户当前阶段可以手动考虑 `vibe-idea`、交互、视觉、原型、架构或实现 Skill；本 Skill 不得直接调用或自动串联。Qima 固定技术栈不匹配时只保留产物思路。

## 数据与部署

- Supabase：需要 PostgreSQL、认证、数据库或对象存储时作为候选；Schema、RLS、迁移、备份、地域和费用必须 Review。
- Vercel 或 Netlify：根据现有框架和团队发布方式选择一个主平台，先 Preview 后生产。
- Provider 迁移不是普通工具选择，必须单独立项和批准。

## GitHub

- 所有 LEVEL 的远程交付读取 `references/github-plugin-routing.md`，Codex 优先选择 GitHub 插件，其他平台可声明现有 CLI/连接器并遵循相同批准与回读要求。
- 插件先只读核对仓库、身份、分支、PR、Tag 和 Release；本地范围配置不替代远程动作时确认。
- push、Draft PR、Merge、Tag 和 Release 先合并为一次动作计划，明确确认后执行并远端回读验证。
- 插件不可用时说明安装或连接要求，可声明受同样治理的替代工具；没有连接则保留待执行计划。

## Windows 命令

遵循安全 PowerShell 规范处理原生命令参数、路径、引号、编码和进程启动。不拼接未验证输入，不跨 Shell 传递删除或移动目标。

## 宣传

生图、视频总结、Remotion、多平台文案和自动上传工具只在产品可公开演示后使用。默认生成素材或草稿；账号授权、隐私、功能承诺和最终公开发布必须人工确认。
