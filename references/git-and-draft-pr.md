# Git 与 Draft PR 执行规范

权限以 risk-and-permissions.md 为准，远程工具与回读见 github-plugin-routing.md。

## 本地切片

Git 项目中，LEVEL 1/2 每个可验证切片在本切片必要检查通过后创建只含当前任务的本地提交，可使用当前分支含默认分支；LEVEL 3 沿用宿主仓库贡献规则。无 Git 的 L1 以变更记录留痕，git init 另需确认。

current_task.paths 声明本轮范围。提交前检查全部修改、暂存区和 Diff，不提交用户无关修改；有用户预先暂存内容时暂停自动提交。运行 git-policy --action local_commit 检查资格。提交后用 git show --stat/--name-status 检查刚创建的提交与剩余工作区，不再次调用要求存在未提交修改的 local_commit 判定。

## 验证证据

用 workflow.py verify --project <项目> -- <命令及参数> 执行必要检查。记录实际退出码、时间、命令、任务标识和项目文件指纹。同一命令重试更新当前结果，其他失败检查仍阻止提交。旧记录保留历史用途；不同任务或内容的 passed 不能授权当前操作。

git-policy 是辅助检查，不是真实用户授权，也不是系统权限边界。未运行的目标平台和集中验收在待验证记录中注明，不用伪造 passed 绕过检查。

## 远程交付

push 自有分支和 Draft PR 的 allow_push_own_branch / allow_create_draft_pr 仅为范围配置。检查身份、仓库、分支、提交与证据后，仍需执行前确认。已提交且工作区干净是正常交付状态，不要求制造新的修改。

删除远程分支、转 Ready、Merge、Tag、Release、公开评论进入具体动作计划；默认分支不自动直推，Force Push 和改写公共历史禁止。Qima 仅可提醒用户手动考虑，不自动调用。
