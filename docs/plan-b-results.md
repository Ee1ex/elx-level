# 方案 B 实施结果

后续版本准备：2026-09-06 将本次改进纳入 2.2，推送状态见 [2.2 交付记录](release/2.2-readiness.md)。以下保留方案 B 实施时的验证快照。

状态：2026-09-05 本地实施及项目要求的验证完成；未推送、未发布、未替换用户现有 Skill 安装。

## 基线与交付位置

- 实施目录：`D:/VibeCoding-Project/elx-level-2.0-worktree`，分支 `codex/plan-b-reliability`。
- 原发布目录：`D:/VibeCoding-Project/elx-level-publish`；收尾确认 HEAD 仍为 `4e1fe169bc4d80ac58bc05d30de6281eb31a72af`，工作区无未提交改动。
- 审查时 GitHub main 为 `e9ee22fbc8d7a027b8b7e9d5f6f489b7511b8d73`；原本地比它多一条提交，差异为 AGENTS.md 和 docs/release/2.1-readiness.md。本次以原本地版本为基线，不覆盖这些约定。
- 公共 VERSION 保持 2.1；本次变更记录在 CHANGELOG 的 Unreleased。四级责任模型及所有历史/兼容模板保留，没有删除项目文件。

## 达到的效果

| 项目 | 修改后的行为与实际效果 | 依据 |
| --- | --- | --- |
| 简单任务流程 | 文案、样式、小配置只需一条记录；局部功能/修复采用一份 Change 或 Bug；多阶段才使用 REQ/PROG，实质取舍再增加 DEC。L1 可以复用 README，不预建空台账 | documentation-contract、LEVEL 与 PVS 规则同步 |
| 入口阅读负担 | SKILL.md 从 136 行 / 5305 字符减至 60 行 / 2480 字符，细则通过引用按需加载 | 与基线提交的文本计数比较；不是 Token 或用时测量 |
| 跨会话接手 | 固定规则→地图→状态→当前任务→相关实现/验证的阅读顺序；区分当前事实、批准未实现、假设、归档 | 新 DOCUMENT_MAP 与治理模板 |
| 规则一致性 | 等级选择和权限分别有统一权威来源；自有开源项目不自动升 L3；L4 批准后的普通执行可继续；其他平台可声明已有 GitHub 工具 | 文档同步，L4 Gate 回归测试 |
| 验证可信度 | verify 实际执行命令并保存退出码；证据绑定任务与 Git 可见文件内容；任务/内容变化、失败证据、未解决 Gate 或人工策略会阻止相应自动操作 | 新鲜度、失败退出、验证期间文件变化及权限回归 |
| 版本变更可靠性 | 只定位项目版本字段，保留依赖版本和配置；已有暂存或版本源脏改时拒绝应用；限定提交文件；无 Tag 可从版本提交推导基线；无新提交不建议升版 | JSON/TOML、暂存保护、BREAKING body、无 Tag 和空增量回归 |
| 状态与迁移 | Schema 与语义校验拒绝无效结构、时间及越界路径；迁移后记录旧来源摘要，来源不变可以重复执行；冲突和无效输入不覆盖已有状态 | 结构校验、幂等、来源改变和无效输入回归 |
| 安装与入口可用性 | 安装文件由统一清单控制，源包及暂存包均校验，同版本残缺安装可保留备份后修复；生成入口定位实际包路径，项目内安装支持随项目移动 | PowerShell 和 Git Bash/POSIX 安装集成、实际安装包校验、适配器移动测试 |

## 验证结果与复现

运行环境：Windows，Python 3.12.14，Git for Windows；临时 PATH 使用 Codex 自带 Python，未修改系统 PATH。

| 检查 | 结果 |
| --- | --- |
| `python -B -m unittest discover -s tests` | 144 项全部通过，24.554 秒；基线 118 项，新增 26 项 |
| `python -B scripts/workflow.py doctor --package-root .` | 全部 PASS，含运行时包资源完整性检查 |
| `python -B scripts/workflow.py validate-package --package-root .` | 通过，elx-level 2.1 |
| `git diff --check` | 通过 |
| Skill Creator 的额外 quick_validate.py | 未完成：当前 Python 缺少 PyYAML，启动时 ModuleNotFoundError；未将其计为通过，也未额外安装依赖 |

测试期间的“拒绝操作”输出来自负面用例，最终 unittest 结果为 OK。安装集成使用临时目录，没有改动用户现有全局 Skill。

## 保留、精简与尚未证明的部分

- 旧 progress-record、change-proposal、deploy-readiness、status 模板保留并标为兼容入口；历史设计保留但退出默认必读路径。
- 自动化校验增强了脚本边界，不保证 Agent 一定遵循所有自然语言文档规则。usage-examples 与 evals 是场景材料，本次没有做真实 Agent 多轮对照评测。
- 尚未测量接手耗时、Token 消耗或长期项目可靠性；不能把入口长度减少折算成运行效率提升比例。
- POSIX 安装器在 Windows Git Bash 实测通过，尚未在原生 Linux/macOS 上复测。
- 验证指纹覆盖 Git 可见文件，不覆盖被忽略文件、外部服务及环境变更；相关任务仍应补充实际验证。
- 动态版本、复杂工作区及锁文件联动不自动猜测。版本提交失败会保留中间状态供检查；迁移遇到磁盘故障不承诺完整事务恢复。多 Agent 并发写同一状态仍需串行协调。
- 项目内 Skill 可随目录移动；引用用户级外部安装的入口，换机或换安装位置后需重新生成。

本地提交按运行时可靠性、规则与文档精简两个主题保存。后续试用和发布属于独立步骤；本次未执行远程写入。
