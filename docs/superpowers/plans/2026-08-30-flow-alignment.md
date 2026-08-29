# 2026-08-30 LEVEL 流程对齐与 Git 提交纪律（执行记录）

> 本文档为回填记录：该批次实施于 2026-08-30，按"回到受影响阶段"回环严格度执行完毕。此文件在实施后补写，用意是让仓库的过程文档惯例（plans/ + CHANGELOG）保持完整。

## 背景与目标

将 ELX Level 的 LEVEL 流程与选定的 AI 产品开发流水线图对齐（环境搭建 → 产品设计[产品方案+Demo] → 技术设计 → 产品实现[写代码+AI 自测] → 人工验证），并补齐 Git 提交纪律与空项目初始化缺口。

## 负责人已确认的决策

1. 自动 `git init` 与"每改动必 commit"仅加入 LEVEL 2（随后扩展为 LEVEL 1/2 提交纪律，LEVEL 3 保持宿主仓库规则）。
2. LEVEL 2 在 G1 需求确认后、G3 技术设计前新增 Demo/原型环节。
3. LEVEL 4 环境搭建加为节点 0（负责人确认实施后、进入后续节点前执行）。
4. Gate 编号理顺为连续的 G0 立项、G1 需求、G2 原型、G3 技术、G4 任务、G5 验收、G6 发布。
5. "需要调整时重走流程"按**回到受影响阶段**的严格度写入 LEVEL 1/2/4，不做字面全量重走。
6. LEVEL 1 计划环节：Brief 即计划（必做功能 + 范围冻结），并新增定稿前假设提问（grilling）义务。

## 变更清单

- `scripts/workflow.py`：新增 `git-init` 子命令（`--confirm` 人工 Gate；只暂存 `.elx-level/` 与 `docs/elx-level/` 基线；已是仓库时拒绝）；`evaluate_git_action` 对 LEVEL 1/2 放宽本地提交到当前分支（含默认分支），LEVEL 3 维持 Skill 自有分支要求。
- `references/git-and-draft-pr.md`：动作矩阵重写 `git init` 与本地提交两行，新增"LEVEL 1/2 切片提交纪律"。
- `references/personal-execution-loop.md`：循环第 6 步写入提交纪律；新增"回环规则"。
- `references/risk-and-permissions.md`：自动允许清单区分 LEVEL 1/2 必须提交与 LEVEL 3 条件允许。
- `templates/level2/demo.md`（新）+ `templates/template-map.json` 注册 `prototype_demo` 角色；`templates/common/acceptance-report.md` Gate 标注 G5；`templates/level1/project-brief.md` 增加实现顺序与验证点说明。
- `LEVEL.md`：LEVEL 1 新增 grilling 与 Brief 即计划；LEVEL 2 插入 G2 Demo 步骤；LEVEL 4 十节点前加节点 0；三级新增回环规则。
- `SKILL.md`：初始化步骤接入 `git-init`；LEVEL 2/4 章节提及新环节；Git 段写入提交纪律。
- `tests/test_git_policy.py`、`tests/test_templates.py`：覆盖新行为。
- `CHANGELOG.md`：`[2.0]` 下新增"流程增补 - 2026-08-30"。

## 顺带修复的基线问题

实施前发现 main 分支已有 6 个测试失败（README 重设计提交未跑测试所致）：英文 README 未同步新版结构、shields.io 徽章与 viewBox 尺寸违反旧契约、安装脚本在 GBK 代码页下重定向输出乱码。处理：重写 `README.en.md` 对齐中文结构，契约测试更新为以新版 README 为准（保留动态统计挂件禁令），`install.ps1` 固定 `[Console]::OutputEncoding` 为 UTF-8。

## 提交与验证

- `a02ac22` fix: realign bilingual README contract and installer output encoding
- `6574fe5` feat: mandatory per-slice commits for LEVEL 1/2 and confirmed git init for LEVEL 2
- `c421834` feat: align LEVEL flow with the AI product development pipeline

验证：`python -m unittest discover -s tests` 全部通过；`doctor` 与 `validate-package` 通过；已通过 `install.ps1` / `update.ps1` 安装到 `~/.codex/skills/elx-level` 与 `~/.zcode/skills/elx-level` 并抽查新文件。
