# 2026-08-30 发布交付自动化：版本号演进与提交描述生成（执行计划）

## 背景与目标

LEVEL 1/2 项目完成 GitHub 交付时，Skill 应自动完成两件事：

1. 为交付相关提交（切片提交、版本提交、PR/Release 描述）生成规范化描述。
2. 自动识别项目版本号格式（X.Y 或 X.Y.Z），按自上个版本以来的改动程度计算并更新版本号。

## 负责人已确认的决策（按推荐执行）

1. 无版本文件的项目：自动创建根 `VERSION` 文件，初始 `0.1`。
2. bump 确认时机：`version-bump` 默认 dry-run 展示分级依据与目标版本，并入 GitHub 交付计划经用户一次确认后 `--apply` 生效。
3. CHANGELOG 联动：目标项目已有 `CHANGELOG.md` 时自动追加本次版本条目；没有则跳过。
4. 不自动创建 Git Tag，只更新版本文件；Tag 留给既有 Release 流程。

## 设计原则

- 本地可恢复动作（改版本文件、创建发布提交）可 AUTO；push/Release 仍走既有 GitHub 插件确认路径。
- 仅 LEVEL 1/2；LEVEL 3 的版本号归宿主仓库维护者管理。
- 单一事实源：版本号写进目标项目现有清单文件，不新建平行记录。
- 分级依据是上个版本以来的提交与验证记录，不做无证据推断；无法判定时降级为 patch 并在计划中列出待确认项。

## 模块设计

### A. 版本源探测

优先级：根 `VERSION` → `package.json` 的 `version` → `pyproject.toml` 首个 `version = "…"` → `Cargo.toml` 首个 `version = "…"`。全部缺失时，`--apply` 创建根 `VERSION`（初始 `0.1`）。

### B. 改动分级

输入：版本 Tag（`v<version>` 或 `<version>`，无 Tag 则全部提交）以来的提交主题。

| 级别 | 判定 |
|---|---|
| major | 主题带 `!`（如 `feat!:`），或提交正文含 `BREAKING CHANGE`，或当前任务风险为 R3/R4 |
| minor | `feat:` / `feat(scope):` |
| patch | `fix:` `docs:` `chore:` `style:` `refactor:` `perf:` `test:` `build:` `ci:` |
| unknown | 无可识别前缀 → 计入 patch，但在计划中列出提醒确认 |

### C. 版本计算与格式保持

检测当前版本的段数并保持：

| 分级 | X.Y.Z | X.Y |
|---|---|---|
| major | X+1.0.0 | X+1.0 |
| minor | X.Y+1.0 | X.Y+1 |
| patch | X.Y.Z+1 | X.Y+1 |

预发布后缀（`-beta.1` 等）保留，只改数字主干。写回时只替换版本字符串。

### D. 文案生成

- 切片提交：`<type>(<scope>): 一句话行为变化`，body 附验证证据。
- 发布提交：`chore(release): v<新版本>`，body 罗列自上版的 feat/fix 清单。
- PR/Release 描述：复用 `templates/common/release-record.md` 字段自动填充。

### E. 流程接入

`集中验收 → version-bump（dry-run）→ 并入 GitHub 交付计划确认 → --apply（写版本 + CHANGELOG + 发布提交）→ push（既有插件路径）`。`--apply` 要求状态中验证记录全部通过；LEVEL 3/4 拒绝执行。

## 文件改动清单

- `scripts/workflow.py`：新增 `version-bump` 子命令。
- `references/release-versioning.md`（新）：探测、分级、计算、文案与确认规则。
- `references/git-and-draft-pr.md`：动作矩阵新增"版本更新与交付提交"。
- `SKILL.md`、`LEVEL.md`：LEVEL 1/2 交付流程接入一句。
- `templates/common/release-record.md`：新增版本来源与分级依据字段。
- `tests/test_version_bump.py`（新）：格式探测、分级、段数映射、写回、发布提交、LEVEL 3 拒绝。
- `CHANGELOG.md`：记录本批。

## 验证方式

`python -m unittest discover -s tests` 全绿；临时仓库集成测试覆盖 dry-run 不落盘、apply 后版本文件与 CHANGELOG 正确、提交只含版本相关文件；`doctor` 与 `validate-package` 通过。
