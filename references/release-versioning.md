# 版本演进与提交规范

用于 LEVEL 1/2 的版本准备；宿主项目规则优先。LEVEL 3 由维护者管理版本。版本提交不等于公开发布，不自动创建 Tag 或 GitHub Release。

## 版本源

按 VERSION、package.json、pyproject.toml、Cargo.toml 查找。JSON 只修改顶层 version；TOML 仅识别 project/tool.poetry 或 package/workspace.package 的字面版本；不修改依赖。动态版本或多个权威来源需人工处理，不能猜测。

## 历史与分级

基线按当前版本 Tag → 匹配的 chore(release) 提交 → 版本源最近提交查找；没有基线时在计划中显示 null 并展示所用历史。读取主题和正文，BREAKING CHANGE 或类型后的 ! 建议 major，feat 建议 minor，其他普通变更建议 patch。R3/R4 不强制 major。没有新提交时不产生新版本。

保持 X.Y 或 X.Y.Z 段数和现有预发布后缀；两段制 patch 与 minor 都增加 Y。复杂工作区、动态版本、多清单或锁文件联动需要使用项目自己的版本工具，本命令不能替代它们。

## 执行

```text
python "<Skill包目录>/scripts/workflow.py" version-bump --project <项目根目录>
python "<Skill包目录>/scripts/workflow.py" version-bump --project <项目根目录> --apply
```

先只读展示版本、基线、分类和提交文案；负责人确认后应用。要求状态有效、允许执行、Git 可用、暂存区为空、当前任务和文件指纹的验证通过。先记录任务，再用 verify 执行检查。存在已有暂存立即拒绝，不改变它。

应用只提交版本源与已有 CHANGELOG。文件写回精确定位；提交失败明确保留中间状态供检查，不盲目再次 apply。版本变化使原证据失效，后续交付前重新验证。

发布提交使用 chore(release): v<版本>，正文记录变更分类。正式交付记录链接已验证的 Commit、版本和实际发布方式；远程动作见 github-plugin-routing.md。
