# Project Vibe Spec 来源与授权

- 原仓库：`https://github.com/dnwwdwd/project-vibe-spec.git`
- 同步提交：`dae5315`（Strengthen cross-module governance gates）
- 纳入版本：`project-level-workflow 0.4.0`
- 授权：源码所有者已确认允许复制、修改并随本包公开分发。
- 许可证：本目录内容统一适用包根目录的 MIT License。

## 文件映射与修改

- 原 `SKILL.md` → `PVS.md`：移除独立 Skill frontmatter，增加包内加载说明；治理规则保持原意。
- 原 `references/` → 本目录 `references/`：内容保持原意。
- 原 `assets/governance-starter/` → 本目录同名路径：模板内容保持原意。
- 原 `README.md` 与 `agents/openai.yaml` 不作为运行时资源复制，因为本包只暴露根 `project-level-workflow` Skill。

## 2026-09-05 本地修订

方案 B 调整任务影响判定、按需建档及项目入口模板，保留来源、许可证和全部模板路径；本次未同步上游内容。
