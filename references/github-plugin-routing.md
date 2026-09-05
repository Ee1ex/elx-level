# GitHub 交付路由

所有 LEVEL 共用目标核对、执行前确认与远端验证要求。Codex 中优先使用 GitHub 插件；Claude Code、Cursor 或插件缺失时，可明确声明使用现有 CLI/连接器，保持同样授权和回读要求，不能静默换用远程写入方式。

## 固定流程

本地验证 → 工具、身份、仓库和分支只读核对 → 具体远程动作计划 → 执行前确认 → 执行 → 远端验证 → 交付记录。

计划只列本次需要的动作，不强制完整跑 push、Draft PR、Merge、Tag、Release。仓库不创建 GitHub Release 或不使用 Tag 时遵守原规则，不把版本记录等同公开发布。

## 计划与授权

说明仓库、身份、base/head、待提交或推送内容、文件范围、验证、回退和未验证项。涉及 PR 时准备标题正文；涉及 Merge 时说明方式；涉及 Tag/Release 时明确目标 Commit 和公开内容。一次批准只涵盖列出的动作，范围变化再次确认。

## 远端验证

- push：远端分支 SHA 与批准提交一致。
- Draft PR：head/base、状态、正文与提交一致。
- Merge：合并状态、方式和目标分支结果。
- Tag：类型和目标 Commit。
- Release：Tag、正文、draft/prerelease 状态和 URL。

读取不一致时按未完成报告，不自动重试高影响动作。没有可用连接时保留本地成果和待执行计划。Force Push 和改写公共历史禁止。
