# 发布版本演进与提交描述规范

## 何时读取

集中验收后准备版本号更新、发布提交、PR 或 Release 描述前读取；仅适用于 LEVEL 1/2。LEVEL 3 的版本号与发布节奏由宿主仓库维护者管理，本 Skill 不代做。

## 命令

```text
python scripts/workflow.py version-bump --project <项目根目录>            # dry-run，展示计划
python scripts/workflow.py version-bump --project <项目根目录> --apply   # 经交付计划确认后应用
```

`--apply` 的前置条件：状态校验通过、验证记录全部通过、当前目录是 Git 仓库。缺一拒绝执行。

## 版本源探测

按优先级取第一个含版本号的文件：

1. 根 `VERSION`（整个文件内容即版本字符串）。
2. `package.json` 的 `version` 字段。
3. `pyproject.toml` 首个 `version = "…"`。
4. `Cargo.toml` 首个 `version = "…"`。

全部缺失时，`--apply` 创建根 `VERSION` 并写入初始 `0.1`（负责人已在交付计划中确认）。

## 改动分级

输入：版本 Tag（`v<version>` 或 `<version>`）以来的全部提交主题；无 Tag 时取全部提交。

| 级别 | 判定 |
|---|---|
| major | 主题带 `!`（如 `feat!:`）、提交正文含 `BREAKING CHANGE`，或当前任务风险为 R3/R4 |
| minor | `feat:` / `feat(scope):` |
| patch | `fix:` `docs:` `chore:` `style:` `refactor:` `perf:` `test:` `build:` `ci:` |
| 降级 | 无可识别前缀的提交按 patch 处理，但在计划中列为 `unknown` 提醒负责人确认 |

## 版本计算

保持现有段数；预发布后缀（`-beta.1` 等）原样保留，只改数字主干。

| 分级 | X.Y.Z | X.Y |
|---|---|---|
| major | X+1.0.0 | X+1.0 |
| minor | X.Y+1.0 | X.Y+1 |
| patch | X.Y.Z+1 | X.Y+1（两段制无 patch 位，修复也进 Y） |

写回时只替换版本字符串本身，不动清单文件的其他内容。

## 文案生成

- 发布提交主题：`chore(release): v<新版本>`；body 罗列分级后的提交清单（minor/major/patch/unknown）。
- 切片提交：`<type>(<scope>): 一句话行为变化`，body 附本轮验证命令与结果。
- PR / Release 描述：复用 `templates/common/release-record.md`，填充版本来源、分级依据、变更清单与验证证据。

## 应用范围与确认

`version-bump` 的 dry-run 计划并入 GitHub 交付计划（见 `github-plugin-routing.md`），负责人一次确认后 `--apply`；只暂存版本文件与 `CHANGELOG.md` 并创建发布提交。目标项目已有 `CHANGELOG.md` 时自动在首个 `##` 小节前插入 `## [<新版本>] - <日期>` 条目；没有则跳过。不自动创建 Git Tag，Tag 与远端动作仍走既有插件确认路径。
