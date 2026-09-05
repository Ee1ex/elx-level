#!/usr/bin/env bash
set -euo pipefail

# 公共包版本必须使用两段版本（X.X）；validate-package 负责拒绝三段版本。
# references/ 与 templates/ 会携带 documentation-contract.md、personal-execution-loop.md、
# level4-capability-routing.md、github-plugin-routing.md、change-record.md、
# release-record.md、architecture.md 和 progress-record.md。

platform=""
scope="user"
project_path="$PWD"
dry_run="false"
mode="install"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --platform) platform="${2:-}"; shift 2 ;;
    --scope) scope="${2:-}"; shift 2 ;;
    --project) project_path="${2:-}"; shift 2 ;;
    --dry-run) dry_run="true"; shift ;;
    --mode) mode="${2:-}"; shift 2 ;;
    *) echo "错误：未知参数：$1" >&2; exit 2 ;;
  esac
done

case "$platform" in codex|claude-code|cursor) ;; *) echo "错误：--platform 必须是 codex、claude-code 或 cursor。" >&2; exit 2 ;; esac
case "$scope" in user|project) ;; *) echo "错误：--scope 必须是 user 或 project。" >&2; exit 2 ;; esac
case "$mode" in install|update) ;; *) echo "错误：内部 mode 无效。" >&2; exit 2 ;; esac

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
package_root="$(CDPATH= cd -- "$script_dir/.." && pwd -P)"
version_file="$package_root/VERSION"
[[ -f "$version_file" ]] || { echo "错误：找不到 VERSION，当前目录不是完整的 elx-level 包。" >&2; exit 1; }
version="$(tr -d '\r\n' < "$version_file")"

if command -v python3 >/dev/null 2>&1; then
  python_cmd="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  python_cmd="$(command -v python)"
else
  echo "错误：安装前包校验需要 Python 3.10+。" >&2
  exit 1
fi
"$python_cmd" "$package_root/scripts/workflow.py" validate-package --package-root "$package_root"
pvs_files="$(find "$package_root/core/project-vibe-spec" -type f | wc -l | tr -d ' ')"
echo "PVS 内核：$pvs_files 个文件"

if [[ "$scope" == "project" ]]; then
  [[ -d "$project_path" ]] || { echo "错误：项目目录不存在：$project_path" >&2; exit 1; }
  base="$(CDPATH= cd -- "$project_path" && pwd -P)"
  case "$platform" in
    codex) target="$base/.codex/skills/elx-level" ;;
    claude-code) target="$base/.claude/skills/elx-level" ;;
    cursor) target="$base/.cursor/skills/elx-level" ;;
  esac
else
  case "$platform" in
    codex) target="${CODEX_HOME:-$HOME/.codex}/skills/elx-level" ;;
    claude-code) target="$HOME/.claude/skills/elx-level" ;;
    cursor) target="$HOME/.cursor/skills/elx-level" ;;
  esac
fi

case "$target" in
  */elx-level) ;;
  *) echo "错误：拒绝操作非托管目标：$target" >&2; exit 1 ;;
esac

independent_pvs="$(dirname -- "$target")/project-vibe-spec"
if [[ -e "$independent_pvs" ]]; then
  echo "提示：检测到独立 project-vibe-spec：$independent_pvs；本安装不处理该目录。"
fi

legacy_target="$(dirname -- "$target")/project-level-workflow"
if [[ -e "$legacy_target" ]]; then
  echo "提示：检测到旧 Skill：$legacy_target；将保留且不会覆盖。"
fi

installed_version_file="$target/VERSION"
if [[ "$mode" == "update" && ! -f "$installed_version_file" ]]; then
  echo "错误：目标未安装，不能更新：$target" >&2
  exit 1
fi

backup=""
if [[ -e "$target" ]]; then
  installed_version="unknown"
  [[ -f "$installed_version_file" ]] && installed_version="$(tr -d '\r\n' < "$installed_version_file")"
  if [[ "$mode" == "install" && "$installed_version" == "$version" ]]; then
    if "$python_cmd" "$package_root/scripts/workflow.py" validate-package --package-root "$target"; then
      echo "elx-level $version 已安装且校验通过：$target"
      exit 0
    fi
    echo '同版本安装不完整，将保留原目录并重新安装。'
  fi
  backup="$target.backup-$(date +%Y%m%d-%H%M%S)"
  [[ ! -e "$backup" ]] || { echo "错误：conflict backup 已存在：$backup" >&2; exit 1; }
fi

echo "模式：$mode；平台：$platform；范围：$scope；版本：$version"
echo "目标：$target"
[[ -z "$backup" ]] || echo "检测到现有安装或修改，将先创建 conflict backup：$backup"
if [[ "$dry_run" == "true" ]]; then
  echo "DryRun：仅显示计划，不写入文件。"
  exit 0
fi

mkdir -p -- "$(dirname -- "$target")"
staging="$target.installing-$$"
[[ ! -e "$staging" ]] || { echo "错误：安装暂存目录已存在：$staging" >&2; exit 1; }
cleanup_install() {
  if [[ -e "$staging" ]]; then
    rm -rf -- "$staging"
  fi
  if [[ ! -e "$target" && -n "$backup" && -e "$backup" ]]; then
    mv -- "$backup" "$target"
  fi
}
trap cleanup_install EXIT

mkdir -p -- "$staging"
items=()
while IFS= read -r item; do item="${item%$'\r'}"; items+=("$item"); done < <(
  "$python_cmd" -c 'import json,sys; print("\n".join(json.load(open(sys.argv[1], encoding="utf-8"))["items"]))' "$package_root/package-files.json"
)
for item in "${items[@]}"; do
  cp -R -- "$package_root/$item" "$staging/"
done
"$python_cmd" "$package_root/scripts/workflow.py" validate-package --package-root "$staging"
[[ -z "$backup" ]] || mv -- "$target" "$backup"
mv -- "$staging" "$target"
trap - EXIT

echo "完成：elx-level $version 已安装到 $target"
[[ -z "$backup" ]] || echo "原版本已保留在：$backup"
