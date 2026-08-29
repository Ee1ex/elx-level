# ELX Level 仓库工作规则

- 本仓库**不创建 GitHub Release**（2026-08-30 负责人决定）：版本演进以根目录 `VERSION` 与 `CHANGELOG.md` 为准，不发布 GitHub Release 页面。
- 安装与更新基于 `git clone` / 安装器脚本，不依赖 Release 资产；不要在文档或脚本中引用 release 下载地址。
- Git tag 保持现状，不随发布自动创建或删除。
- 改动纪律：每个主题一个提交，交付前 `python -m unittest discover -s tests` 全部通过，并运行 `doctor` 与 `validate-package`。
