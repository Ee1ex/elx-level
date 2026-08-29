#!/usr/bin/env python3
"""ELX Level 的确定性状态管理 CLI。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from urllib.parse import unquote


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "elx-level"
PRODUCT_NAME = "ELX Level"
SCHEMA_VERSION = "2.0"
STATE_DIR_NAME = ".elx-level"
LEGACY_STATE_DIR_NAME = ".project-workflow"
DOCS_DIR_NAME = "elx-level"
LEGACY_SCHEMA_VERSIONS = {"0.9.0", "1.0.0", "1.1.0"}
TWO_PART_VERSION = re.compile(r"^\d+\.\d+$")
LEGACY_THREE_PART_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
REQUIRED_FIELDS = (
    "schema_version",
    "workflow_version",
    "project_id",
    "level",
    "stage",
    "gate",
    "status",
    "risk",
    "execution_policy",
    "permissions",
    "current_task",
    "artifacts",
    "verifications",
    "git",
    "remote",
    "history",
    "updated_at",
)
SENSITIVE_KEY_PARTS = ("password", "secret", "token", "api_key", "private_key")
MANAGED_START = "<!-- elx-level:start -->"
MANAGED_END = "<!-- elx-level:end -->"
LEVEL_DOCUMENT = "LEVEL.md"
PVS_CORE = Path("core/project-vibe-spec")
PVS_TEMPLATE_MAP = Path("templates/template-map.json")
PVS_CORE_FILES = (
    "PVS.md",
    "SOURCE.md",
    "references/decision-gates.md",
    "references/document-maintenance.md",
)
EXTERNAL_PVS_INSTALL = re.compile(
    r"(?:git\s+clone[^\n]*project-vibe-spec|skills[/\\]project-vibe-spec|\$project-vibe-spec)",
    re.IGNORECASE,
)
LEVEL_REFERENCES = {
    1: "LEVEL.md#level-1快速开发与完整项目记忆",
    2: "LEVEL.md#level-2完整-pvs-持续运营",
    3: "LEVEL.md#level-3已有团队与开源项目改进",
    4: "LEVEL.md#level-4复杂自动化参考与路由",
}
LEGACY_LEVEL_MIGRATION = {
    1: 1,
    2: 3,
    3: 4,
}
LEVEL_MODES = {
    1: "快速开发与完整记忆：稳定认知 + Ledger/小记录，执行—运行—观察—调整。",
    2: "完整 PVS：Phase 0 → Phase N、范围冻结和 DoD；普通 Phase 自动推进。",
    3: "已有仓库改进：复用 Issue、PR、CHANGELOG、ADR，保留 Change Record、基线、回归与交接。",
    4: "复杂自动化参考：先分析，负责人确认后可实施；专业能力只做外部路由。",
}
INITIAL_STAGE = {
    1: "project-memory",
    2: "phase-0",
    3: "repository-intake",
    4: "requirements-analysis",
}
DEFAULT_EXECUTION_POLICY = {1: "AUTO", 2: "AUTO", 3: "AUTO", 4: "CONFIRM"}


def configure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_version() -> str:
    version_path = PACKAGE_ROOT / "VERSION"
    if not version_path.is_file():
        raise ValueError("缺少 VERSION 文件")
    version = version_path.read_text(encoding="utf-8").strip()
    if not TWO_PART_VERSION.fullmatch(version):
        raise ValueError(f"VERSION 必须是两段版本（X.X）：{version}")
    return version


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    temporary.write_text(content, encoding="utf-8", newline="\n")
    json.loads(temporary.read_text(encoding="utf-8"))
    temporary.replace(path)


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    normalized = content.rstrip() + "\n"
    temporary.write_text(normalized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def build_initial_state(project: Path, level: int) -> dict[str, Any]:
    project_name = project.name or "project"
    digest = hashlib.sha256(str(project).encode("utf-8")).hexdigest()[:8]
    now = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "workflow_version": load_version(),
        "project_id": f"{project_name}-{digest}",
        "level": level,
        "stage": INITIAL_STAGE[level],
        "gate": None,
        "status": "in_progress",
        "risk": "R1",
        "execution_policy": DEFAULT_EXECUTION_POLICY[level],
        "permissions": {
            "allow_push_own_branch": False,
            "allow_create_draft_pr": False,
        },
        "current_task": None,
        "artifacts": [],
        "verifications": [],
        "git": {
            "repository": False,
            "branch": None,
            "skill_created_branch": False,
            "last_commit": None,
        },
        "remote": {
            "name": None,
            "url": None,
            "draft_pr": None,
        },
        "history": [
            {
                "event": "workflow_initialized",
                "stage": INITIAL_STAGE[level],
                "at": now,
            }
        ],
        "updated_at": now,
    }


def _refresh_workflow_version(state: dict[str, Any]) -> bool:
    current = load_version()
    previous = state.get("workflow_version")
    if previous == current:
        return False
    now = utc_now()
    state["workflow_version"] = current
    state["updated_at"] = now
    state["history"].append(
        {
            "event": "workflow_version_updated",
            "from_version": previous,
            "to_version": current,
            "at": now,
        }
    )
    return True


def _iter_values(value: Any, path: str = ""):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            yield child_path, key, child
            yield from _iter_values(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            yield child_path, str(index), child
            yield from _iter_values(child, child_path)


def _is_absolute_file_path(value: str) -> bool:
    if value.startswith(("http://", "https://")):
        return False
    return PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute()


def validate_state(data: dict[str, Any], project: Path) -> list[str]:
    del project
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["状态根节点必须是对象"]
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"缺少必填字段：{field}")

    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"不支持的 schema_version：{data.get('schema_version')}")
    workflow_version = data.get("workflow_version")
    if not isinstance(workflow_version, str) or not (
        TWO_PART_VERSION.fullmatch(workflow_version)
        or LEGACY_THREE_PART_VERSION.fullmatch(workflow_version)
    ):
        errors.append("workflow_version 必须是两段版本或兼容的历史三段版本")
    if data.get("level") not in (1, 2, 3, 4):
        errors.append("level 只允许 1、2、3 或 4")
    if data.get("risk") not in ("R1", "R2", "R3", "R4"):
        errors.append("risk 只允许 R1、R2、R3 或 R4")
    if data.get("execution_policy") not in ("AUTO", "CONFIRM", "MANUAL_ONLY"):
        errors.append("execution_policy 只允许 AUTO、CONFIRM 或 MANUAL_ONLY")
    if data.get("status") not in ("in_progress", "waiting_approval", "completed", "blocked"):
        errors.append("status 值无效")

    permissions = data.get("permissions")
    if not isinstance(permissions, dict):
        errors.append("permissions 必须是对象")
    else:
        for name in ("allow_push_own_branch", "allow_create_draft_pr"):
            if not isinstance(permissions.get(name), bool):
                errors.append(f"permissions.{name} 必须是布尔值")

    for field in ("artifacts", "verifications", "history"):
        if field in data and not isinstance(data[field], list):
            errors.append(f"{field} 必须是数组")
    for field in ("git", "remote"):
        if field in data and not isinstance(data[field], dict):
            errors.append(f"{field} 必须是对象")

    for value_path, key, value in _iter_values(data):
        lowered = key.lower()
        if any(part in lowered for part in SENSITIVE_KEY_PARTS):
            errors.append(f"状态禁止保存敏感字段：{value_path}")
        if isinstance(value, str) and _is_absolute_file_path(value):
            errors.append(f"状态路径必须相对项目根目录：{value_path}")
    return errors


def _initial_status(state: dict[str, Any]) -> str:
    return render_status(state)


def _format_items(items: list[Any], empty_message: str) -> str:
    if not items:
        return f"- {empty_message}"
    lines: list[str] = []
    for item in items:
        if isinstance(item, dict):
            summary = item.get("summary") or item.get("path") or item.get("command")
            lines.append(f"- {summary or json.dumps(item, ensure_ascii=False)}")
        else:
            lines.append(f"- {item}")
    return "\n".join(lines)


def _migration_status(state: dict[str, Any]) -> str:
    history = state.get("history") or []
    migrations = [
        event
        for event in history
        if isinstance(event, dict)
        and event.get("event")
        in {"level_migrated", "level_reconfirmed", "workflow_schema_migrated"}
    ]
    if not migrations:
        return "- 无等级迁移记录。"
    event = migrations[-1]
    old_level = event.get("old_level", "未知")
    new_level = event.get("new_level", "未知")
    from_schema = event.get("from_schema", "未知")
    to_schema = event.get("to_schema", state.get("schema_version", "未知"))
    reason = event.get("reason", "未记录")
    confirmation = event.get("approved_by") or "无；未自动批准 Gate"
    return "\n".join(
        [
            f"- 旧 LEVEL：{old_level}",
            f"- 新 LEVEL：{new_level}",
            f"- 迁移版本：Schema {from_schema} → {to_schema}",
            f"- 迁移原因：{reason}",
            f"- 用户重确认：{confirmation}",
            (
                f"- 迁移后的 Gate 未自动批准：`{state['gate']}`。"
                if state.get("gate")
                else "- 本次迁移未新增人工 Gate。"
            ),
        ]
    )


def render_status(data: dict[str, Any]) -> str:
    task = data.get("current_task") or {}
    task_summary = task.get("summary") or task.get("title") or "尚未创建任务"
    scope = task.get("scope") or "当前任务范围尚未写入状态。"
    exclusions = task.get("out_of_scope") or "未记录额外排除项。"
    gate = data.get("gate")
    artifacts = _format_items(data.get("artifacts", []), "尚无已记录产物。")
    verifications = _format_items(data.get("verifications", []), "尚无已记录验证。")
    level_four = data["level"] == 4
    open_questions = task.get("open_questions")
    show_risk = (
        level_four
        or data["risk"] in {"R3", "R4"}
        or data["execution_policy"] != "AUTO"
        or bool(open_questions)
    )
    risk_section = ""
    if show_risk:
        risk_section = f"""
## 当前风险与未决事项

- 风险等级：{data['risk']}
- 未决事项：{open_questions or '无已记录未决事项。'}
"""
    gate_section = ""
    if level_four or gate:
        gate_section = f"""
## 当前人工 Gate

{gate or '当前没有等待批准的 Gate。'}
"""
    gate_metadata = (
        f"- 关联 Gate：{gate}\n"
        if gate
        else ("- 关联 Gate：当前没有等待批准的 Gate。\n" if level_four else "")
    )
    return f"""# 项目流程状态

- 状态：{data['status']}
- 负责人：{task.get('owner') or '待项目负责人确认'}
- 执行策略：{data['execution_policy']}
{gate_metadata.rstrip()}
- 最后更新时间：{data['updated_at']}

## 当前 LEVEL、阶段与任务

LEVEL {data['level']} / {data['stage']} / {task_summary}

## 本轮目标与不做范围

- 范围：{scope}
- 本次不做：{exclusions}

## 已完成内容

{artifacts}

## 验证命令与结果摘要

{verifications}
{risk_section}{gate_section}

## 最近等级迁移

{_migration_status(data)}

## 推荐选择与下一步

{task.get('next_step') or f"读取 `{LEVEL_REFERENCES[data['level']]}`，选择下一个最小可验收任务。"}
"""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"状态文件不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"状态 JSON 无法解析：第 {exc.lineno} 行第 {exc.colno} 列") from exc


def command_init(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        print(f"项目目录不存在：{project}", file=sys.stderr)
        return 1
    state_dir = project / STATE_DIR_NAME
    state_path = state_dir / "state.json"
    backup_path = state_dir / "state.backup.json"
    status_path = project / "docs" / DOCS_DIR_NAME / "STATUS.md"
    legacy_state_dir = project / LEGACY_STATE_DIR_NAME
    if legacy_state_dir.exists() and not state_dir.exists():
        print(
            f"发现旧状态目录 {legacy_state_dir}；请先运行 migrate 完成复制迁移",
            file=sys.stderr,
        )
        return 2
    if legacy_state_dir.exists() and state_dir.exists():
        print("新旧状态目录同时存在；请人工核对，未覆盖任何状态", file=sys.stderr)
        return 2

    previous: dict[str, Any] | None = None
    if state_path.exists():
        if not args.force:
            print("状态已经存在；如需重新初始化，请显式使用 --force", file=sys.stderr)
            return 2
        try:
            previous = _load_json(state_path)
        except ValueError as exc:
            print(f"无法备份现有状态：{exc}", file=sys.stderr)
            return 1

    state = build_initial_state(project, args.level)
    errors = validate_state(state, project)
    if errors:
        print("初始化状态无效：\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1

    if previous is not None:
        atomic_write_json(backup_path, previous)
    else:
        atomic_write_json(backup_path, state)
    atomic_write_json(state_path, state)
    atomic_write_text(status_path, _initial_status(state))
    print(f"已初始化 LEVEL {args.level} 项目流程：{project}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    try:
        state_path, _, _ = _require_current_state_paths(project)
        state = _load_json(state_path)
    except ValueError as exc:
        print(f"状态无效：\n- {exc}", file=sys.stderr)
        return 1
    errors = validate_state(state, project)
    if errors:
        print("状态无效：\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    print(f"状态有效：LEVEL {state['level']} / {state['stage']} / {state['status']}")
    return 0


def _state_paths(project: Path) -> tuple[Path, Path, Path]:
    state_dir = project / STATE_DIR_NAME
    return (
        state_dir / "state.json",
        state_dir / "state.backup.json",
        project / "docs" / DOCS_DIR_NAME / "STATUS.md",
    )


def _require_current_state_paths(project: Path) -> tuple[Path, Path, Path]:
    paths = _state_paths(project)
    legacy_state = project / LEGACY_STATE_DIR_NAME / "state.json"
    if not paths[0].is_file() and legacy_state.is_file():
        raise ValueError(
            f"发现旧状态 {legacy_state}；请运行 migrate 复制到 {STATE_DIR_NAME}"
        )
    return paths


def _copy_legacy_state(project: Path) -> tuple[tuple[Path, Path, Path], bool]:
    legacy = project / LEGACY_STATE_DIR_NAME
    current = project / STATE_DIR_NAME
    if legacy.exists() and current.exists():
        raise FileExistsError("新旧状态目录同时存在；请人工核对，未覆盖任何状态")
    if not legacy.exists():
        return _state_paths(project), False
    legacy_state = _load_json(legacy / "state.json")
    source_schema = legacy_state.get("schema_version")
    if source_schema == SCHEMA_VERSION:
        errors = validate_state(legacy_state, project)
        if errors:
            raise ValueError("旧状态无效：" + "；".join(errors))
    elif source_schema not in LEGACY_SCHEMA_VERSIONS:
        raise ValueError(f"不支持从 Schema {source_schema} 迁移")
    shutil.copytree(legacy, current)
    return _state_paths(project), True


def command_status(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    try:
        state_path, backup_path, status_path = _require_current_state_paths(project)
        state = _load_json(state_path)
    except ValueError as exc:
        print(f"状态无效：\n- {exc}", file=sys.stderr)
        return 1
    errors = validate_state(state, project)
    if errors:
        print("状态无效：\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    previous = json.loads(json.dumps(state, ensure_ascii=False))
    if _refresh_workflow_version(state):
        errors = validate_state(state, project)
        if errors:
            print("版本刷新后状态无效：\n- " + "\n- ".join(errors), file=sys.stderr)
            return 1
        atomic_write_json(backup_path, previous)
        atomic_write_json(state_path, state)
    atomic_write_text(status_path, render_status(state))
    print(f"已刷新状态摘要：{status_path}")
    return 0


def command_transition(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    try:
        state_path, backup_path, status_path = _require_current_state_paths(project)
        state = _load_json(state_path)
    except ValueError as exc:
        print(f"状态无效：\n- {exc}", file=sys.stderr)
        return 1
    errors = validate_state(state, project)
    if errors:
        print("状态无效：\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    if state.get("gate") != args.approve_gate:
        print(
            f"Gate 不匹配：当前为 {state.get('gate')}，请求批准 {args.approve_gate}",
            file=sys.stderr,
        )
        return 2
    approved_by = args.approved_by.strip()
    if not approved_by:
        print("approved-by 不能为空", file=sys.stderr)
        return 1

    previous = json.loads(json.dumps(state, ensure_ascii=False))
    _refresh_workflow_version(state)
    now = utc_now()
    state["stage"] = args.to_stage
    state["gate"] = args.next_gate
    state["status"] = "waiting_approval" if args.next_gate else "in_progress"
    state["execution_policy"] = (
        "CONFIRM" if args.next_gate else DEFAULT_EXECUTION_POLICY[state["level"]]
    )
    state["updated_at"] = now
    state["history"].append(
        {
            "event": "gate_approved",
            "gate": args.approve_gate,
            "to_stage": args.to_stage,
            "approved_by": approved_by,
            "at": now,
        }
    )
    errors = validate_state(state, project)
    if errors:
        print("转换后状态无效：\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    atomic_write_json(backup_path, previous)
    atomic_write_json(state_path, state)
    atomic_write_text(status_path, render_status(state))
    print(f"已批准 {args.approve_gate}，进入阶段 {args.to_stage}")
    return 0


def command_migrate(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    try:
        (state_path, backup_path, status_path), copied_legacy = _copy_legacy_state(project)
        state = _load_json(state_path)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"状态无效：\n- {exc}", file=sys.stderr)
        return 1
    source_version = state.get("schema_version")
    if source_version == SCHEMA_VERSION:
        errors = validate_state(state, project)
        if errors:
            print("状态无效：\n- " + "\n- ".join(errors), file=sys.stderr)
            return 1
        if copied_legacy:
            previous = json.loads(json.dumps(state, ensure_ascii=False))
            _refresh_workflow_version(state)
            errors = validate_state(state, project)
            if errors:
                print("品牌迁移后状态无效：\n- " + "\n- ".join(errors), file=sys.stderr)
                return 1
            atomic_write_json(backup_path, previous)
            atomic_write_json(state_path, state)
            atomic_write_text(status_path, render_status(state))
            print(
                f"已复制旧状态到 {STATE_DIR_NAME}；旧目录保持不变，后续只使用新路径"
            )
            return 0
        print("状态 Schema 已是最新版本")
        return 0
    if source_version not in LEGACY_SCHEMA_VERSIONS:
        print(f"不支持从 Schema {source_version} 迁移", file=sys.stderr)
        return 1

    old_level = state.get("level")
    if source_version == "1.1.0":
        if old_level not in (1, 2, 3, 4):
            print("0.4.0 状态的 level 必须是 LEVEL 1、2、3 或 4", file=sys.stderr)
            return 1
    elif old_level not in LEGACY_LEVEL_MIGRATION:
        print("旧状态的 level 必须是旧 LEVEL 1、2 或 3", file=sys.stderr)
        return 1

    explicit_target = getattr(args, "target_level", None)
    approved_by = (getattr(args, "approved_by", None) or "").strip()
    reason = (getattr(args, "reason", None) or "").strip()
    if source_version == "1.1.0":
        if explicit_target is not None or approved_by or reason:
            print("0.4.0 状态迁移保持现有 LEVEL，不接受旧等级重映射参数", file=sys.stderr)
            return 2
        new_level = old_level
        migration_event_name = "workflow_schema_migrated"
        migration_reason = "从 0.4.0 状态协议迁移；保留已确认的 LEVEL 1–4 语义。"
    elif explicit_target is not None:
        if explicit_target != 2 or old_level != 3:
            print(
                "只有旧 LEVEL 3 可以通过显式重确认改为新 LEVEL 2",
                file=sys.stderr,
            )
            return 2
        if not approved_by or not reason:
            print("改为新 LEVEL 2 必须同时提供 approved-by 和 reason", file=sys.stderr)
            return 2
        new_level = explicit_target
        migration_event_name = "level_reconfirmed"
        migration_reason = reason
    else:
        if approved_by or reason:
            print("approved-by 和 reason 只能与 --target-level 2 一起使用", file=sys.stderr)
            return 2
        new_level = LEGACY_LEVEL_MIGRATION[old_level]
        migration_event_name = "level_migrated"
        migration_reason = (
            f"兼容迁移旧 LEVEL {old_level} 的数字语义："
            f"旧 LEVEL {old_level} → 新 LEVEL {new_level}。"
        )

    previous = json.loads(json.dumps(state, ensure_ascii=False))
    now = utc_now()
    state["schema_version"] = SCHEMA_VERSION
    state["workflow_version"] = load_version()
    state["level"] = new_level
    if source_version == "1.1.0" and old_level == 4:
        state["gate"] = "level4-execution-review"
        state["status"] = "waiting_approval"
    elif source_version != "1.1.0":
        state["gate"] = "level-migration-review"
        state["status"] = "waiting_approval"
    state["execution_policy"] = (
        "CONFIRM" if state.get("gate") else DEFAULT_EXECUTION_POLICY[new_level]
    )
    state.setdefault(
        "permissions",
        {
            "allow_push_own_branch": False,
            "allow_create_draft_pr": False,
        },
    )
    state.setdefault("history", []).append(
        {
            "event": migration_event_name,
            "old_level": old_level,
            "new_level": new_level,
            "from_schema": source_version,
            "to_schema": SCHEMA_VERSION,
            "reason": migration_reason,
            **({"approved_by": approved_by} if approved_by else {}),
            "at": now,
        }
    )
    state["updated_at"] = now
    errors = validate_state(state, project)
    if errors:
        print("迁移后状态无效：\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    atomic_write_json(backup_path, previous)
    atomic_write_json(state_path, state)
    atomic_write_text(status_path, render_status(state))
    gate_summary = (
        f"Gate {state['gate']} 等待人工确认"
        if state.get("gate")
        else "未新增人工 Gate"
    )
    print(
        f"已从 Schema {source_version} 迁移到 {SCHEMA_VERSION}；"
        f"旧 LEVEL {old_level} → 新 LEVEL {new_level}；{gate_summary}"
    )
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    root = Path(args.package_root).expanduser().resolve()
    checks: list[tuple[str, bool, str]] = []
    checks.append(("Python 3.10+", sys.version_info >= (3, 10), sys.version.split()[0]))
    checks.append(("Git 命令", shutil.which("git") is not None, shutil.which("git") or "未发现"))

    checks.append(("统一 LEVEL.md", (root / LEVEL_DOCUMENT).is_file(), "根目录唯一等级流程"))
    for relative in [
        "SKILL.md",
        "VERSION",
        "schemas/workflow-state.schema.json",
        "references/level-selection.md",
        "references/risk-and-permissions.md",
        "references/state-protocol.md",
        "references/tool-routing.md",
        "references/platform-compatibility.md",
        "references/project-vibe-spec-bridge.md",
        "references/documentation-contract.md",
        "references/personal-execution-loop.md",
        "references/level4-capability-routing.md",
        "references/github-plugin-routing.md",
        "docs/release/2.0-readiness.md",
        "adapters/codex/AGENTS.fragment.md",
        "adapters/claude-code/CLAUDE.fragment.md",
        "adapters/cursor/elx-level.mdc",
    ]:
        path = root / relative
        checks.append((relative, path.is_file(), str(path)))

    schema_path = root / "schemas" / "workflow-state.schema.json"
    schema_valid = False
    if schema_path.is_file():
        try:
            json.loads(schema_path.read_text(encoding="utf-8"))
            schema_valid = True
        except (OSError, json.JSONDecodeError):
            schema_valid = False
    checks.append(("状态 Schema JSON", schema_valid, str(schema_path)))

    pvs_errors = _embedded_pvs_errors(root)
    checks.append(
        (
            "PVS 包内内核",
            not pvs_errors,
            "; ".join(pvs_errors) or str(root / PVS_CORE),
        )
    )
    checks.append(
        (
            "PVS 模板职责映射",
            (root / PVS_TEMPLATE_MAP).is_file(),
            str(root / PVS_TEMPLATE_MAP),
        )
    )

    if args.project:
        project = Path(args.project).expanduser().resolve()
        state_path = project / STATE_DIR_NAME / "state.json"
        state_valid = False
        if state_path.is_file():
            try:
                state_valid = not validate_state(_load_json(state_path), project)
            except ValueError:
                state_valid = False
        checks.append(("项目状态", state_valid, str(state_path)))

    required_failures = 0
    for name, passed, detail in checks:
        if name == "Git 命令" and not passed:
            print(f"WARN {name}：{detail}")
            continue
        marker = "PASS" if passed else "FAIL"
        print(f"{marker} {name}：{detail}")
        if not passed:
            required_failures += 1
    independent_pvs = root.parent / "project-vibe-spec"
    if independent_pvs.is_dir():
        print(
            f"WARN 独立 project-vibe-spec：{independent_pvs}；"
            "本包不会读取、覆盖或删除该目录。"
        )
    return 1 if required_failures else 0


def _managed_block(content: str) -> str:
    start = content.find(MANAGED_START)
    end = content.find(MANAGED_END)
    if start < 0 or end < start:
        raise ValueError("适配器模板缺少托管区块标记")
    return content[start : end + len(MANAGED_END)]


def _merge_managed_content(existing: str, rendered: str) -> str:
    block = _managed_block(rendered)
    start = existing.find(MANAGED_START)
    end = existing.find(MANAGED_END)
    if start >= 0 and end >= start:
        suffix_start = end + len(MANAGED_END)
        merged = existing[:start].rstrip() + "\n\n" + block + existing[suffix_start:]
        return merged.strip() + "\n"
    if not existing.strip():
        return rendered.strip() + "\n"
    return existing.rstrip() + "\n\n" + block + "\n"


def _write_with_backup(path: Path, content: str) -> None:
    if path.exists():
        backup = path.with_name(f"{path.name}.elx-level.bak")
        atomic_write_text(backup, path.read_text(encoding="utf-8"))
    atomic_write_text(path, content)


def command_render_adapter(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    try:
        state_path, _, _ = _require_current_state_paths(project)
        state = _load_json(state_path)
    except ValueError as exc:
        print(f"状态无效：\n- {exc}", file=sys.stderr)
        return 1
    errors = validate_state(state, project)
    if errors:
        print("状态无效：\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1

    definitions = {
        "codex": (
            PACKAGE_ROOT / "adapters" / "codex" / "AGENTS.fragment.md",
            project / "AGENTS.md",
        ),
        "claude-code": (
            PACKAGE_ROOT / "adapters" / "claude-code" / "CLAUDE.fragment.md",
            project / "CLAUDE.md",
        ),
        "cursor": (
            PACKAGE_ROOT / "adapters" / "cursor" / "elx-level.mdc",
            project / ".cursor" / "rules" / "elx-level.mdc",
        ),
    }
    template_path, target_path = definitions[args.platform]
    if not template_path.is_file():
        print(f"适配器模板不存在：{template_path}", file=sys.stderr)
        return 1
    rendered = template_path.read_text(encoding="utf-8")
    rendered = rendered.replace("{{LEVEL}}", str(state["level"]))
    rendered = rendered.replace("{{LEVEL_DOC}}", LEVEL_REFERENCES[state["level"]])
    rendered = rendered.replace("{{LEVEL_MODE}}", LEVEL_MODES[state["level"]])

    if target_path.exists():
        existing = target_path.read_text(encoding="utf-8")
        content = _merge_managed_content(existing, rendered)
    else:
        content = rendered.strip() + "\n"
    _write_with_backup(target_path, content)
    print(f"已生成 {args.platform} 项目入口：{target_path}")
    return 0


def _git_output(project: Path, *arguments: str) -> tuple[int, str]:
    git = shutil.which("git")
    if not git:
        return 127, ""
    completed = subprocess.run(
        [git, *arguments],
        cwd=project,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return completed.returncode, completed.stdout.rstrip()


def inspect_git(project: Path) -> dict[str, Any]:
    project = project.expanduser().resolve()
    result: dict[str, Any] = {
        "available": shutil.which("git") is not None,
        "repository": False,
        "branch": None,
        "default_branch": None,
        "changed_files": [],
        "changes_in_scope": None,
        "unrelated_changes": [],
        "remote_name": None,
        "remote_url": None,
        "authenticated": False,
        "ahead_commits": 0,
    }
    if not result["available"] or not project.is_dir():
        return result
    code, inside = _git_output(project, "rev-parse", "--is-inside-work-tree")
    if code != 0 or inside.lower() != "true":
        return result
    result["repository"] = True

    code, branch = _git_output(project, "branch", "--show-current")
    if code == 0 and branch:
        result["branch"] = branch

    code, status = _git_output(project, "status", "--porcelain=v1", "--untracked-files=all")
    if code == 0 and status:
        changed: list[str] = []
        for line in status.splitlines():
            path = line[3:] if len(line) > 3 else line
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            changed.append(path.strip('"').replace("\\", "/"))
        result["changed_files"] = changed

    code, remotes = _git_output(project, "remote")
    if code == 0 and remotes:
        names = [name for name in remotes.splitlines() if name]
        remote_name = "origin" if "origin" in names else names[0]
        result["remote_name"] = remote_name
        _, remote_url = _git_output(project, "remote", "get-url", remote_name)
        result["remote_url"] = remote_url or None
        _, remote_head = _git_output(
            project, "symbolic-ref", "--quiet", "--short", f"refs/remotes/{remote_name}/HEAD"
        )
        if remote_head.startswith(f"{remote_name}/"):
            result["default_branch"] = remote_head.split("/", 1)[1]
        if branch:
            ahead_code, ahead = _git_output(
                project, "rev-list", "--count", f"{remote_name}/{branch}..HEAD"
            )
            if ahead_code == 0 and ahead.isdigit():
                result["ahead_commits"] = int(ahead)
    return result


def _verifications_passed(state: dict[str, Any]) -> bool:
    verifications = state.get("verifications")
    if not isinstance(verifications, list) or not verifications:
        return False
    accepted = {"pass", "passed", "ok", "success", "成功", "通过"}
    for verification in verifications:
        if not isinstance(verification, dict):
            return False
        status = str(verification.get("status") or verification.get("result") or "").lower()
        if status not in accepted:
            return False
    return True


def _changes_are_in_scope(state: dict[str, Any], git_info: dict[str, Any]) -> bool:
    explicit = git_info.get("changes_in_scope")
    if isinstance(explicit, bool):
        return explicit
    changed = git_info.get("changed_files") or []
    task = state.get("current_task") or {}
    paths = task.get("paths") or []
    if not changed or not paths:
        return False
    normalized = [str(path).strip("/").replace("\\", "/") for path in paths]
    return all(
        any(file == allowed or file.startswith(f"{allowed}/") for allowed in normalized)
        for file in changed
    )


def evaluate_git_action(
    action: str, state: dict[str, Any], git_info: dict[str, Any]
) -> dict[str, Any]:
    supported = {
        "git_init",
        "create_branch",
        "local_commit",
        "push_own_branch",
        "create_draft_pr",
        "force_push",
        "rewrite_history",
        "delete_remote_branch",
        "ready_pr",
        "merge",
        "tag",
        "release",
    }
    if action not in supported:
        raise ValueError(f"未知 Git 动作：{action}")
    decision: dict[str, Any] = {
        "action": action,
        "allowed": False,
        "requires_gate": False,
        "reasons": [],
    }
    reasons: list[str] = decision["reasons"]

    if action in {"force_push", "rewrite_history"}:
        reasons.append("禁止 Force Push 或改写公共历史；任何 Gate 都不能覆盖。")
        return decision
    if action in {
        "delete_remote_branch",
        "ready_pr",
        "merge",
        "tag",
        "release",
    }:
        decision["requires_gate"] = True
        reasons.append("必须进入 GitHub 插件远程动作计划，并在执行前取得明确确认。")
        return decision
    if action == "git_init":
        decision["requires_gate"] = True
        reasons.append("Git 初始化会改变项目治理边界，必须先通过人工 Gate。")
        return decision

    if not git_info.get("available"):
        reasons.append("未发现 Git 命令。")
    if not git_info.get("repository"):
        reasons.append("当前目录不是 Git 仓库。")
    if state.get("risk") not in {"R1", "R2"}:
        reasons.append("只有 R1/R2 任务可自动执行本地 Git 动作。")
    if not isinstance(state.get("current_task"), dict) or not state.get("current_task"):
        reasons.append("缺少已确认的 current_task。")

    if action == "create_branch":
        decision["allowed"] = not reasons
        return decision

    personal_level = state.get("level") in (1, 2)
    if not personal_level and not (state.get("git") or {}).get("skill_created_branch"):
        reasons.append("当前分支不是本 Skill 创建或明确接管的分支。")
    if not git_info.get("branch"):
        reasons.append("无法识别当前分支。")
    if not git_info.get("changed_files"):
        reasons.append("没有可提交的文件修改。")
    if not _changes_are_in_scope(state, git_info):
        reasons.append("修改超出 current_task 声明范围。")
    if git_info.get("unrelated_changes"):
        reasons.append("检测到用户无关修改，禁止纳入自动提交。")
    if not _verifications_passed(state):
        reasons.append("尚无完整通过的验证证据。")

    if action == "local_commit":
        decision["allowed"] = not reasons
        return decision

    permissions = state.get("permissions") or {}
    branch = git_info.get("branch")
    default_branch = git_info.get("default_branch")
    if not permissions.get("allow_push_own_branch"):
        reasons.append("permissions.allow_push_own_branch=false。")
    if branch in {"main", "master", default_branch}:
        reasons.append("禁止自动写入默认分支。")
    if not git_info.get("remote_name") or not git_info.get("remote_url"):
        reasons.append("未配置可确认的 Git Remote。")
    if not git_info.get("authenticated"):
        reasons.append("尚未确认远端身份验证。")
    if int(git_info.get("ahead_commits") or 0) < 1:
        reasons.append("当前分支没有待推送提交。")

    if action == "create_draft_pr" and not permissions.get("allow_create_draft_pr"):
        reasons.append("permissions.allow_create_draft_pr=false。")

    if reasons:
        return decision
    decision["requires_gate"] = True
    reasons.append("远程写入必须进入 GitHub 插件动作计划并取得执行前明确确认。")
    return decision


def command_git_policy(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    try:
        state_path, _, _ = _require_current_state_paths(project)
        state = _load_json(state_path)
    except ValueError as exc:
        print(f"状态无效：\n- {exc}", file=sys.stderr)
        return 1
    errors = validate_state(state, project)
    if errors:
        print("状态无效：\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    git_info = inspect_git(project)
    if args.authenticated:
        git_info["authenticated"] = True
    decision = evaluate_git_action(args.action, state, git_info)
    print(json.dumps({"decision": decision, "git": git_info}, ensure_ascii=False, indent=2))
    return 0 if decision["allowed"] else 2


def command_git_init(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        print(f"项目目录不存在：{project}", file=sys.stderr)
        return 1
    git = shutil.which("git")
    if not git:
        print("未发现 Git 命令，无法初始化仓库。", file=sys.stderr)
        return 1
    if (project / ".git").exists():
        print("当前目录已是 Git 仓库；未执行任何操作。", file=sys.stderr)
        return 2
    if not args.confirm:
        print(
            "Git 初始化是人工 Gate：取得用户确认后，使用 --confirm 重新执行。",
            file=sys.stderr,
        )
        return 2
    result = subprocess.run([git, "init"], cwd=project, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"git init 失败：\n{(result.stderr or result.stdout).strip()}", file=sys.stderr)
        return 1
    state_path = project / STATE_DIR_NAME / "state.json"
    if not state_path.is_file():
        print(f"已初始化 Git 仓库（尚未运行 init，跳过基线提交）：{project}")
        return 0
    scaffold = [STATE_DIR_NAME, f"docs/{DOCS_DIR_NAME}"]
    existing = [path for path in scaffold if Path(project / path).exists()]
    add_result = subprocess.run(
        [git, "add", "--", *existing], cwd=project, capture_output=True, text=True
    )
    if add_result.returncode != 0:
        print(
            "已初始化 Git 仓库，但暂存工作流基线失败：\n"
            f"{(add_result.stderr or add_result.stdout).strip()}",
            file=sys.stderr,
        )
        return 1
    commit_result = subprocess.run(
        [git, "commit", "-m", args.message, "--", *existing],
        cwd=project,
        capture_output=True,
        text=True,
    )
    if commit_result.returncode != 0:
        print(
            "已初始化 Git 仓库，但基线提交失败：\n"
            f"{(commit_result.stderr or commit_result.stdout).strip()}",
            file=sys.stderr,
        )
        return 1
    print(f"已初始化 Git 仓库并提交工作流基线：{project}")
    return 0


def _public_markdown_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in root.rglob("*.md"):
        relative = path.relative_to(root).as_posix()
        if relative.startswith(
            ("docs/superpowers/", "tests/", f"{STATE_DIR_NAME}/", f"{LEGACY_STATE_DIR_NAME}/")
        ):
            continue
        if "__pycache__" in path.parts:
            continue
        paths.append(path)
    return sorted(paths)


def _markdown_table_errors(path: Path, text: str) -> list[str]:
    errors: list[str] = []
    groups: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines() + [""]:
        if line.strip().startswith("|") and line.strip().endswith("|"):
            current.append(line.strip())
        elif current:
            groups.append(current)
            current = []
    separator = re.compile(r"^\|(?:\s*:?-{3,}:?\s*\|)+$")
    for index, group in enumerate(groups, start=1):
        if len(group) < 2 or not any(separator.fullmatch(line) for line in group):
            errors.append(f"{path.name} 的第 {index} 个 Markdown 表格缺少有效分隔行")
    return errors


def _markdown_link_errors(root: Path, path: Path, text: str) -> list[str]:
    errors: list[str] = []
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
        raw_target = match.group(1).strip().strip("<>")
        target = raw_target.split("#", 1)[0].strip()
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if " " in target:
            target = target.split(" ", 1)[0]
        candidate = (path.parent / unquote(target)).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            errors.append(f"{path.relative_to(root)} 的相对链接越出包目录：{raw_target}")
            continue
        if not candidate.exists():
            errors.append(f"{path.relative_to(root)} 的相对链接不存在：{raw_target}")
    return errors


def _embedded_pvs_errors(root: Path) -> list[str]:
    errors: list[str] = []
    core = root / PVS_CORE
    for relative in PVS_CORE_FILES:
        if not (core / relative).is_file():
            errors.append(f"PVS 内核缺少文件：{PVS_CORE / relative}")
    if (core / "SKILL.md").exists():
        errors.append(
            "PVS 内核不得包含第二个 Skill 入口：core/project-vibe-spec/SKILL.md"
        )
    source_path = core / "SOURCE.md"
    if source_path.is_file():
        try:
            source = source_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"PVS 来源记录无法读取：{exc}")
        else:
            for marker in ("dnwwdwd/project-vibe-spec", "dae5315", "MIT"):
                if marker not in source:
                    errors.append(f"PVS 来源记录缺少：{marker}")

    map_path = root / PVS_TEMPLATE_MAP
    if not map_path.is_file():
        errors.append(f"PVS 模板职责映射不存在：{PVS_TEMPLATE_MAP}")
        return errors
    try:
        data = json.loads(map_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"PVS 模板职责映射无法读取：{exc}")
        return errors
    roles = data.get("roles")
    if data.get("version") != 1 or not isinstance(roles, list) or not roles:
        errors.append("PVS 模板职责映射必须包含 version=1 和非空 roles")
        return errors
    names: set[str] = set()
    defaults: set[str] = set()
    for entry in roles:
        if not isinstance(entry, dict):
            errors.append("PVS 模板职责条目必须是对象")
            continue
        name = entry.get("name")
        default = entry.get("default")
        if not isinstance(name, str) or not name or name in names:
            errors.append(f"PVS 模板职责名称无效或重复：{name}")
        else:
            names.add(name)
        if not isinstance(default, str) or not default or default in defaults:
            errors.append(f"PVS 默认模板无效或重复：{default}")
        else:
            defaults.add(default)
            if not (root / default).is_file():
                errors.append(f"PVS 默认模板不存在：{default}")
        compatibility = entry.get("compatibility", [])
        if not isinstance(compatibility, list):
            errors.append(f"PVS compatibility 必须是数组：{name}")
            continue
        for relative in compatibility:
            if not isinstance(relative, str) or not (root / relative).is_file():
                errors.append(f"PVS 兼容模板不存在：{relative}")
    return errors


def validate_package(root: Path) -> list[str]:
    root = root.expanduser().resolve()
    errors: list[str] = []
    required = [
        "SKILL.md",
        "README.md",
        "VERSION",
        "CHANGELOG.md",
        "LICENSE",
        LEVEL_DOCUMENT,
        "schemas/workflow-state.schema.json",
        "evals/evals.json",
        "docs/release/2.0-readiness.md",
        "core/project-vibe-spec/PVS.md",
        "core/project-vibe-spec/SOURCE.md",
        "core/project-vibe-spec/references/decision-gates.md",
        "core/project-vibe-spec/references/document-maintenance.md",
        "templates/template-map.json",
        "references/level-selection.md",
        "references/risk-and-permissions.md",
        "references/state-protocol.md",
        "references/tool-routing.md",
        "references/platform-compatibility.md",
        "references/git-and-draft-pr.md",
        "references/project-vibe-spec-bridge.md",
        "references/documentation-contract.md",
        "references/personal-execution-loop.md",
        "references/level4-capability-routing.md",
        "references/github-plugin-routing.md",
        "adapters/codex/AGENTS.fragment.md",
        "adapters/claude-code/CLAUDE.fragment.md",
        "adapters/cursor/elx-level.mdc",
        "scripts/install.ps1",
        "scripts/install.sh",
        "scripts/update.ps1",
        "scripts/update.sh",
        "scripts/uninstall.ps1",
        "scripts/uninstall.sh",
    ]
    for relative in required:
        if not (root / relative).is_file():
            errors.append(f"缺少公共包文件：{relative}")
    errors.extend(_embedded_pvs_errors(root))
    if errors:
        return errors

    try:
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
        schema = json.loads(
            (root / "schemas" / "workflow-state.schema.json").read_text(encoding="utf-8")
        )
        evals = json.loads((root / "evals" / "evals.json").read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
        return [f"公共合同无法读取：{exc}"]
    if not TWO_PART_VERSION.fullmatch(version):
        errors.append("VERSION 必须是两段版本（X.X）")
    if schema.get("properties", {}).get("workflow_version", {}).get("const") != version:
        errors.append("Schema workflow_version 与 VERSION 不一致")
    if schema.get("properties", {}).get("level", {}).get("enum") != [1, 2, 3, 4]:
        errors.append("Schema level.enum 必须是 [1, 2, 3, 4]")
    if evals.get("version") != version:
        errors.append("evals 版本与 VERSION 不一致")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## [{version}]" not in changelog:
        errors.append("CHANGELOG 未登记当前 VERSION")

    private_paths = ("C:\\Users\\", "D:\\VibeCodingFiles", "/Users/")
    secret_patterns = (
        re.compile(r"ghp_[A-Za-z0-9]{20,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    )
    unfinished = re.compile(r"\b(?:TODO|TBD|FIXME|CHANGEME)\b", re.IGNORECASE)
    markdown_files = _public_markdown_files(root)
    for path in markdown_files:
        relative = path.relative_to(root)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"Markdown 不是有效 UTF-8：{relative}")
            continue
        if not any(line.startswith("#") for line in text.splitlines()):
            errors.append(f"Markdown 缺少标题：{relative}")
        for value in private_paths:
            if value in text:
                errors.append(f"公共文件包含个人绝对路径：{relative}")
        if unfinished.search(text):
            errors.append(f"公共 Markdown 包含未完成占位词：{relative}")
        for pattern in secret_patterns:
            if pattern.search(text):
                errors.append(f"公共 Markdown 疑似包含密钥：{relative}")
        if relative != PVS_CORE / "SOURCE.md" and EXTERNAL_PVS_INSTALL.search(text):
            errors.append(f"公共文件包含外部 PVS 安装或调用要求：{relative}")
        errors.extend(_markdown_table_errors(path, text))
        errors.extend(_markdown_link_errors(root, path, text))

    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    if len(skill.splitlines()) >= 500:
        errors.append("SKILL.md 必须少于 500 行")
    if "Qima" not in skill or "不得直接调用" not in skill:
        errors.append("SKILL.md 缺少 Qima reminder-only 边界")
    if "allow_push_own_branch=false" not in skill or "allow_create_draft_pr=false" not in skill:
        errors.append("SKILL.md 缺少公开远程权限默认关闭声明")

    permission_properties = schema.get("properties", {}).get("permissions", {}).get("properties", {})
    for name in ("allow_push_own_branch", "allow_create_draft_pr"):
        if permission_properties.get(name, {}).get("default") is not False:
            errors.append(f"Schema 中 {name} 必须默认 false")

    for relative in (
        "adapters/codex/AGENTS.fragment.md",
        "adapters/claude-code/CLAUDE.fragment.md",
        "adapters/cursor/elx-level.mdc",
    ):
        adapter = (root / relative).read_text(encoding="utf-8")
        if (
            "{{LEVEL}}" not in adapter
            or "{{LEVEL_DOC}}" not in adapter
            or "{{LEVEL_MODE}}" not in adapter
        ):
            errors.append(f"适配器未使用统一 LEVEL/LEVEL_DOC/LEVEL_MODE 占位：{relative}")
    root_level_docs = sorted(path.name for path in root.glob("LEVEL*.md"))
    if root_level_docs != [LEVEL_DOCUMENT]:
        errors.append("根目录必须只保留统一 LEVEL.md，不得保留分散或旧版 LEVEL 文档")
    return errors


def command_validate_package(args: argparse.Namespace) -> int:
    root = Path(args.package_root).expanduser().resolve()
    errors = validate_package(root)
    if errors:
        print("包验证失败：\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    print(f"包验证通过：{PACKAGE_NAME} {(root / 'VERSION').read_text(encoding='utf-8').strip()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"{PRODUCT_NAME} 状态工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="初始化项目流程状态")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--level", required=True, type=int, choices=(1, 2, 3, 4))
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(handler=command_init)

    validate_parser = subparsers.add_parser("validate", help="校验项目流程状态")
    validate_parser.add_argument("--project", required=True)
    validate_parser.set_defaults(handler=command_validate)

    status_parser = subparsers.add_parser("status", help="刷新人类可读状态摘要")
    status_parser.add_argument("--project", required=True)
    status_parser.set_defaults(handler=command_status)

    transition_parser = subparsers.add_parser("transition", help="批准 Gate 并转换阶段")
    transition_parser.add_argument("--project", required=True)
    transition_parser.add_argument("--approve-gate", required=True)
    transition_parser.add_argument("--to-stage", required=True)
    transition_parser.add_argument("--approved-by", required=True)
    transition_parser.add_argument("--next-gate")
    transition_parser.set_defaults(handler=command_transition)

    migrate_parser = subparsers.add_parser("migrate", help="迁移项目状态 Schema")
    migrate_parser.add_argument("--project", required=True)
    migrate_parser.add_argument(
        "--target-level",
        type=int,
        choices=(2,),
        help="仅旧 LEVEL 3 可显式重确认到新 LEVEL 2",
    )
    migrate_parser.add_argument("--approved-by", help="新 LEVEL 2 重确认的用户或角色")
    migrate_parser.add_argument("--reason", help="新 LEVEL 2 重确认原因")
    migrate_parser.set_defaults(handler=command_migrate)

    doctor_parser = subparsers.add_parser("doctor", help="检查 Skill 包和项目环境")
    doctor_parser.add_argument("--package-root", default=str(PACKAGE_ROOT))
    doctor_parser.add_argument("--project")
    doctor_parser.set_defaults(handler=command_doctor)

    adapter_parser = subparsers.add_parser("render-adapter", help="生成平台项目入口")
    adapter_parser.add_argument("--platform", required=True, choices=("codex", "claude-code", "cursor"))
    adapter_parser.add_argument("--project", required=True)
    adapter_parser.set_defaults(handler=command_render_adapter)

    git_init_parser = subparsers.add_parser(
        "git-init", help="经用户确认后初始化 Git 仓库并提交工作流基线"
    )
    git_init_parser.add_argument("--project", required=True)
    git_init_parser.add_argument(
        "--confirm", action="store_true", help="显式携带用户确认；缺少时不执行"
    )
    git_init_parser.add_argument(
        "--message", default="chore: initialize elx-level workflow state"
    )
    git_init_parser.set_defaults(handler=command_git_init)

    git_parser = subparsers.add_parser("git-policy", help="检查 Git 动作是否满足自动执行条件")
    git_parser.add_argument("--project", required=True)
    git_parser.add_argument(
        "--action",
        required=True,
        choices=(
            "git_init",
            "create_branch",
            "local_commit",
            "push_own_branch",
            "create_draft_pr",
            "force_push",
            "rewrite_history",
            "delete_remote_branch",
            "ready_pr",
            "merge",
            "release",
        ),
    )
    git_parser.add_argument(
        "--authenticated",
        action="store_true",
        help="调用方已通过独立工具确认远端身份有效",
    )
    git_parser.set_defaults(handler=command_git_policy)

    package_parser = subparsers.add_parser("validate-package", help="执行发布前全包静态校验")
    package_parser.add_argument("--package-root", default=str(PACKAGE_ROOT))
    package_parser.set_defaults(handler=command_validate_package)
    return parser


def main() -> int:
    configure_utf8_output()
    try:
        args = build_parser().parse_args()
        return int(args.handler(args))
    except (OSError, ValueError) as exc:
        print(f"执行失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
