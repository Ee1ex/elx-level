#!/usr/bin/env python3
"""ELX Level 的确定性状态管理 CLI。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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


def _schema_errors(value: Any, rule: dict[str, Any], path: str = "state") -> list[str]:
    errors = []
    expected = rule.get("type")
    types = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
             "string": lambda x: isinstance(x, str), "boolean": lambda x: type(x) is bool,
             "null": lambda x: x is None, "integer": lambda x: type(x) is int}
    if expected and not any(types[kind](value) for kind in ([expected] if isinstance(expected, str) else expected)):
        return [f"{path} 类型不符合 Schema"]
    if "const" in rule and value != rule["const"]:
        errors.append(f"{path} 不符合 Schema 固定值")
    if "enum" in rule and not any(type(value) is type(item) and value == item for item in rule["enum"]):
        errors.append(f"{path} 不在 Schema 枚举中")
    if isinstance(value, str):
        if len(value) < rule.get("minLength", 0) or (rule.get("pattern") and not re.search(rule["pattern"], value)):
            errors.append(f"{path} 格式不符合 Schema")
        if rule.get("format") == "date-time" and not _valid_timestamp(value):
            errors.append(f"{path} 必须是带时区时间")
    if isinstance(value, dict):
        properties = rule.get("properties", {})
        for key in rule.get("required", []):
            if key not in value:
                errors.append(f"缺少必填字段：{path}.{key}")
        for key, child in value.items():
            if key in properties:
                errors.extend(_schema_errors(child, properties[key], f"{path}.{key}"))
            elif rule.get("additionalProperties") is False:
                errors.append(f"{path}.{key} 是未知字段")
    if isinstance(value, list) and "items" in rule:
        for index, item in enumerate(value):
            errors.extend(_schema_errors(item, rule["items"], f"{path}[{index}]"))
    return errors


def validate_state(data: dict[str, Any], project: Path) -> list[str]:
    del project
    schema = json.loads((PACKAGE_ROOT / "schemas/workflow-state.schema.json").read_text(encoding="utf-8"))
    errors: list[str] = _schema_errors(data, schema)
    if not isinstance(data, dict):
        return ["状态根节点必须是对象"]
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"缺少必填字段：{field}")

    for field in set(data) - set(REQUIRED_FIELDS):
        errors.append(f"未知状态字段：{field}")
    for field in ("project_id", "stage"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            errors.append(f"{field} 必须是非空字符串")
    if data.get("gate") is not None and not isinstance(data["gate"], str):
        errors.append("gate 必须是字符串或 null")
    task = data.get("current_task")
    if task is not None and not isinstance(task, dict):
        errors.append("current_task 必须是对象或 null")
    elif isinstance(task, dict) and "paths" in task:
        paths = task["paths"]
        if not isinstance(paths, list) or any(
            not isinstance(item, str) or not item or ".." in PurePosixPath(item.replace(chr(92), "/")).parts
            for item in paths
        ):
            errors.append("current_task.paths 必须是项目内相对路径数组")
    if not _valid_timestamp(data.get("updated_at")):
        errors.append("updated_at 必须是带时区的 ISO 8601 时间")
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"不支持的 schema_version：{data.get('schema_version')}")
    workflow_version = data.get("workflow_version")
    if not isinstance(workflow_version, str) or not (
        TWO_PART_VERSION.fullmatch(workflow_version)
        or LEGACY_THREE_PART_VERSION.fullmatch(workflow_version)
    ):
        errors.append("workflow_version 必须是两段版本或兼容的历史三段版本")
    elif tuple(int(part) for part in workflow_version.split(".")) > tuple(int(part) for part in load_version().split(".")):
        errors.append("workflow_version 来自未来版本；不能自动降级")
    if type(data.get("level")) is not int or data.get("level") not in (1, 2, 3, 4):
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
        if set(permissions) - {"allow_push_own_branch", "allow_create_draft_pr"}:
            errors.append("permissions 包含未知字段")
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


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).utcoffset() is not None
    except ValueError:
        return False


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
    if legacy_state.parent.exists() and paths[0].parent.exists():
        _check_retained_legacy(project)
    if not paths[0].is_file() and legacy_state.is_file():
        raise ValueError(
            f"发现旧状态 {legacy_state}；请运行 migrate 复制到 {STATE_DIR_NAME}"
        )
    return paths


def _copy_legacy_state(project: Path) -> tuple[tuple[Path, Path, Path], bool]:
    legacy = project / LEGACY_STATE_DIR_NAME
    current = project / STATE_DIR_NAME
    if legacy.exists() and current.exists():
        try:
            _check_retained_legacy(project)
        except ValueError as exc:
            raise FileExistsError(str(exc)) from exc
        return _state_paths(project), False
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
    # Read from the retained source first. Do not create a destination until the
    # transformed state is fully validated (invalid input must be retryable).
    return (legacy / "state.json", legacy / "state.backup.json", _state_paths(project)[2]), True


def _legacy_digest(project: Path) -> str:
    return hashlib.sha256((project / LEGACY_STATE_DIR_NAME / "state.json").read_bytes()).hexdigest()


def _check_retained_legacy(project: Path) -> None:
    state = _load_json(project / STATE_DIR_NAME / "state.json")
    history = state.get("history", [])
    try:
        digest = _legacy_digest(project)
    except OSError as exc:
        raise ValueError("旧状态不可读取；请人工核对") from exc
    if not isinstance(history, list) or not any(
        isinstance(event, dict) and event.get("event") == "legacy_state_retained"
        and event.get("source_sha256") == digest for event in history
    ):
        raise ValueError("新旧状态目录同时存在且缺少匹配迁移记录；请人工核对，未覆盖任何状态")


def _record_retained_legacy(state: dict[str, Any], project: Path) -> None:
    state.setdefault("history", []).append({
        "event": "legacy_state_retained", "source_sha256": _legacy_digest(project), "at": utc_now()
    })


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
        "CONFIRM" if args.next_gate or state["risk"] == "R3" else ("MANUAL_ONLY" if state["risk"] == "R4" else "AUTO")
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
            _record_retained_legacy(state, project)
            errors = validate_state(state, project)
            if errors:
                print("品牌迁移后状态无效：\n- " + "\n- ".join(errors), file=sys.stderr)
                return 1
            shutil.copytree(project / LEGACY_STATE_DIR_NAME, project / STATE_DIR_NAME)
            state_path, backup_path, status_path = _state_paths(project)
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
    if copied_legacy:
        _record_retained_legacy(state, project)
    errors = validate_state(state, project)
    if errors:
        print("迁移后状态无效：\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    if copied_legacy:
        shutil.copytree(project / LEGACY_STATE_DIR_NAME, project / STATE_DIR_NAME)
        state_path, backup_path, status_path = _state_paths(project)
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

    package_errors = validate_package(root)
    checks.append(("运行时包闭包", not package_errors, "；".join(package_errors) or "安装清单及引用完整"))
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
    try:
        package_location = PACKAGE_ROOT.relative_to(project).as_posix()
    except ValueError:
        package_location = PACKAGE_ROOT.as_posix()
    rendered = rendered.replace("{{PACKAGE_ROOT}}", package_location)
    rendered = rendered.replace("{{LEVEL_DOC}}", package_location + "/" + LEVEL_REFERENCES[state["level"]])
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

    code, status = _git_output(project, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if code == 0 and status:
        changed: list[str] = []
        records = iter(status.split(chr(0)))
        for record in records:
            if not record:
                continue
            changed.append(record[3:])
            if "R" in record[:2] or "C" in record[:2]:
                changed.append(next(records, ""))
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
    result["fingerprint"] = project_fingerprint(project)
    return result


def task_identity(state: dict[str, Any]) -> str:
    task = state.get("current_task")
    if not isinstance(task, dict) or not task:
        return ""
    identity = {key: task.get(key) for key in ("id", "title", "summary", "scope", "paths", "out_of_scope")}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def project_fingerprint(project: Path) -> str:
    code, output = _git_output(project, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if code:
        return ""
    digest = hashlib.sha256()
    for name in sorted(set(output.split(chr(0))) - {""}):
        if name.startswith((STATE_DIR_NAME + "/", LEGACY_STATE_DIR_NAME + "/")) or name == "docs/elx-level/STATUS.md":
            continue
        path = project / name
        digest.update(name.encode("utf-8") + bytes([0]))
        if path.is_symlink():
            digest.update(b"link:" + os.readlink(path).encode("utf-8"))
        elif path.is_file():
            digest.update(b"file:" + path.read_bytes())
        else:
            digest.update(b"missing")
        digest.update(bytes([0]))
    return digest.hexdigest()


def _verifications_passed(state: dict[str, Any], git_info: dict[str, Any] | None = None) -> bool:
    verifications = state.get("verifications")
    task_id = task_identity(state)
    fingerprint = (git_info or {}).get("fingerprint")
    if not task_id or not fingerprint or not isinstance(verifications, list) or not verifications:
        return False
    # Historical evidence remains readable; only the current task and content qualify.
    current = [item for item in verifications if isinstance(item, dict)
               and item.get("task_id") == task_id and item.get("fingerprint") == fingerprint]
    if not current:
        return False
    return all(item.get("status") == "passed" and item.get("exit_code") == 0
               and bool(item.get("command")) and _valid_timestamp(item.get("at"))
               for item in current)


def command_verify(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    try:
        state_path, backup_path, status_path = _require_current_state_paths(project)
        state = _load_json(state_path)
        errors = validate_state(state, project)
        if errors:
            raise ValueError("；".join(errors))
        if not task_identity(state):
            raise ValueError("请先记录已确认的 current_task，再执行验证")
        command = list(args.command)
        if command and command[0] == "--":
            command.pop(0)
        if not command:
            raise ValueError("verify 需要 -- 后的验证命令和参数")
        before = project_fingerprint(project)
        if not before:
            raise ValueError("verify 需要可读取的 Git 项目；非 Git 项目在变更记录中保留人工验证")
        result = subprocess.run(command, cwd=project, check=False, shell=False)
        after = project_fingerprint(project)
        if result.returncode == 0 and before != after:
            raise ValueError("验证改变了项目文件；未登记通过，请检查变化后重新验证")
        previous = json.loads(json.dumps(state))
        display_command = [Path(command[0]).name, *command[1:]]
        entry = {"command": subprocess.list2cmdline(display_command), "status": "passed" if result.returncode == 0 else "failed",
                 "exit_code": result.returncode, "at": utc_now(), "task_id": task_identity(state), "fingerprint": after}
        state["verifications"] = [item for item in state["verifications"] if not (
            isinstance(item, dict) and item.get("task_id") == entry["task_id"]
            and item.get("fingerprint") == after and item.get("command") == entry["command"])] + [entry]
        state["updated_at"] = utc_now()
        errors = validate_state(state, project)
        if errors:
            raise ValueError("验证记录无效：" + "；".join(errors))
        atomic_write_json(backup_path, previous)
        atomic_write_json(state_path, state)
        atomic_write_text(status_path, render_status(state))
        return 0 if result.returncode == 0 else 1
    except (ValueError, OSError) as exc:
        print(f"验证未通过：{exc}", file=sys.stderr)
        return 1


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

    if state.get("status") not in {"in_progress", "completed"} or state.get("gate") or state.get("execution_policy") != "AUTO":
        reasons.append("状态、Gate 或执行策略不允许自动 Git 动作。")
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
    if action == "local_commit" and not git_info.get("changed_files"):
        reasons.append("没有可提交的文件修改。")
    if git_info.get("changed_files") and not _changes_are_in_scope(state, git_info):
        reasons.append("修改超出 current_task 声明范围。")
    if git_info.get("unrelated_changes"):
        reasons.append("检测到用户无关修改，禁止纳入自动提交。")
    if not _verifications_passed(state, git_info):
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


VERSION_SOURCE_ORDER = ("VERSION", "package.json", "pyproject.toml", "Cargo.toml")
MAJOR_SUBJECT_PATTERN = re.compile(r"^[A-Za-z]+(\([^)]*\))?!\s*:")
MINOR_SUBJECT_PATTERN = re.compile(r"^feat(\([^)]*\))?\s*:")
PATCH_SUBJECT_PATTERN = re.compile(
    r"^(fix|docs|chore|style|refactor|perf|test|build|ci)(\([^)]*\))?\s*:"
)
BREAKING_CHANGE_PATTERN = re.compile(r"BREAKING\s*CHANGE", re.IGNORECASE)


def _manifest_version(text: str, kind: str) -> tuple[str, int, int] | None:
    if kind == "package_json":
        if not isinstance(json.loads(text), dict):
            raise ValueError("package.json 必须是对象")
        decoder = json.JSONDecoder()
        cursor = text.index("{") + 1
        found = []
        while True:
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            if text[cursor] == "}":
                break
            key, cursor = decoder.raw_decode(text, cursor)
            while text[cursor].isspace():
                cursor += 1
            if text[cursor] != ":":
                raise ValueError("无效 JSON 字段")
            cursor += 1
            while text[cursor].isspace():
                cursor += 1
            start = cursor
            value, cursor = decoder.raw_decode(text, cursor)
            if key == "version":
                if not isinstance(value, str):
                    raise ValueError("项目 version 必须是字符串")
                found.append((value, start, cursor))
            while text[cursor].isspace():
                cursor += 1
            if text[cursor] == ",":
                cursor += 1
            elif text[cursor] != "}":
                raise ValueError("无效 JSON 分隔符")
        if len(found) > 1:
            raise ValueError("重复的项目 version 字段")
        return found[0] if found else None
    sections = {"project", "tool.poetry"} if kind == "pyproject.toml" else {"package", "workspace.package"}
    section = ""
    offset = 0
    found = []
    for line in text.splitlines(keepends=True):
        header = re.match(r"\s*\[([^\[\]]+)\]\s*(?:#.*)?$", line.strip())
        if header:
            section = header.group(1).strip()
        elif line.lstrip().startswith("["):
            section = ""
        if section in sections and re.match(r"\s*(?:version\.workspace|dynamic)\s*=", line) and "version" in line:
            raise ValueError("动态或继承的版本需要项目自己的版本工具")
        match = re.match(r"""\s*version\s*=\s*(["'])([^"'\r\n]+)\1\s*(?:#.*)?$""", line.rstrip("\r\n"))
        if section in sections and match:
            found.append((match.group(2), offset + match.start(1), offset + match.end(2) + 1))
        offset += len(line)
    if len(found) > 1:
        raise ValueError("存在多个项目版本来源，请明确唯一权威版本")
    return found[0] if found else None


def detect_version_source(project: Path) -> dict[str, Any] | None:
    for name in VERSION_SOURCE_ORDER:
        path = project / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if name == "VERSION":
            if text.strip():
                return {"path": path, "kind": "version_file", "version": text.strip()}
        else:
            kind = "package_json" if name == "package.json" else name
            located = _manifest_version(text, kind)
            if located:
                return {"path": path, "kind": kind, "version": located[0]}
    return None


def classify_commit_subjects(subjects: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {"major": [], "minor": [], "patch": [], "unknown": []}
    for subject in subjects:
        if MAJOR_SUBJECT_PATTERN.match(subject) or BREAKING_CHANGE_PATTERN.search(subject):
            groups["major"].append(subject)
        elif MINOR_SUBJECT_PATTERN.match(subject):
            groups["minor"].append(subject)
        elif PATCH_SUBJECT_PATTERN.match(subject):
            groups["patch"].append(subject)
        else:
            groups["unknown"].append(subject)
    return groups


def highest_change_level(groups: dict[str, list[str]]) -> str:
    if groups["major"]:
        return "major"
    if groups["minor"]:
        return "minor"
    return "patch"


def commits_since_version_tag(project: Path, version: str) -> tuple[list[str], str | None]:
    baseline = None
    for candidate in (f"v{version}", version):
        code, _ = _git_output(project, "rev-parse", "-q", "--verify", f"refs/tags/{candidate}")
        if code == 0:
            code, _ = _git_output(project, "merge-base", "--is-ancestor", candidate, "HEAD")
            if code:
                raise ValueError("版本 Tag 不在当前历史中，请确认版本基线")
            baseline = candidate
            break
    if baseline is None:
        code, log = _git_output(project, "log", "--format=%H%x00%s")
        if code:
            raise ValueError("无法读取提交历史")
        for line in log.splitlines():
            sha, _, subject = line.partition(chr(0))
            if subject == f"chore(release): v{version}":
                baseline = sha
                break
        if baseline is None:
            source = detect_version_source(project)
            if source:
                code, sha = _git_output(project, "log", "-1", "--format=%H", "--", source["path"].name)
                if code == 0 and sha:
                    baseline = sha
    arguments = ["log", "--format=%B%x00"]
    if baseline:
        arguments.append(f"{baseline}..HEAD")
    code, output = _git_output(project, *arguments)
    if code:
        raise ValueError("无法读取版本基线之后的提交")
    return [message.strip() for message in output.split(chr(0)) if message.strip()], baseline


def compute_next_version(current: str, level: str) -> str:
    main, separator, suffix = current.partition("-")
    parts = main.split(".")
    if len(parts) > 3:
        raise ValueError(f"不支持的版本号格式：{current}")
    try:
        numbers = [int(part) for part in parts]
    except ValueError as exc:
        raise ValueError(f"无法解析版本号：{current}") from exc
    if len(numbers) == 3:
        if level == "major":
            numbers = [numbers[0] + 1, 0, 0]
        elif level == "minor":
            numbers = [numbers[0], numbers[1] + 1, 0]
        else:
            numbers = [numbers[0], numbers[1], numbers[2] + 1]
        next_main = ".".join(str(number) for number in numbers)
    else:
        while len(numbers) < 2:
            numbers.append(0)
        if level == "major":
            next_main = f"{numbers[0] + 1}.0"
        else:
            next_main = f"{numbers[0]}.{numbers[1] + 1}"
    return f"{next_main}{separator}{suffix}" if separator else next_main


def write_version_to_source(source: dict[str, Any], new_version: str) -> None:
    path = source["path"]
    if path.is_symlink():
        raise ValueError("版本文件不能是符号链接")
    text = path.read_text(encoding="utf-8")
    if source["kind"] == "version_file":
        if text.strip() != source["version"]:
            raise ValueError("版本源在计划后发生变化")
        atomic_write_text(path, new_version)
        return
    located = _manifest_version(text, source["kind"])
    if not located or located[0] != source["version"]:
        raise ValueError("无法定位批准的项目版本字段")
    _, start, end = located
    quote = text[start]
    updated = text[:start] + quote + new_version + quote + text[end:]
    if _manifest_version(updated, source["kind"])[0] != new_version:
        raise ValueError("版本写回校验失败")
    atomic_write_text(path, updated)


def update_project_changelog(
    changelog: Path, new_version: str, groups: dict[str, list[str]]
) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    bullets: list[str] = []
    for group_name in ("minor", "major", "patch", "unknown"):
        for subject in groups[group_name]:
            bullets.append(f"- {subject}")
    if not bullets:
        bullets.append("- 本次无按前缀分类的提交。")
    block = f"## [{new_version}] - {today}\n\n" + "\n".join(bullets) + "\n\n"
    text = changelog.read_text(encoding="utf-8")
    head, separator, rest = text.partition("\n## ")
    if separator:
        new_text = head.rstrip("\n") + "\n\n" + block + "## " + rest
    elif text.startswith("#"):
        first_line, _, remainder = text.partition("\n")
        new_text = first_line + "\n\n" + block + remainder.lstrip("\n")
    else:
        new_text = block + text
    changelog.write_text(new_text, encoding="utf-8")


def command_version_bump(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        print(f"项目目录不存在：{project}", file=sys.stderr)
        return 1
    try:
        state_path, _, _ = _require_current_state_paths(project)
        state = _load_json(state_path)
        errors = validate_state(state, project)
        if errors:
            raise ValueError("；".join(errors))
    except ValueError as exc:
        print(f"状态无效：{exc}", file=sys.stderr)
        return 1
    if state.get("level") not in (1, 2):
        print(
            "version-bump 仅支持 LEVEL 1/2 项目；LEVEL 3 的版本号由宿主仓库维护者管理。",
            file=sys.stderr,
        )
        return 2
    git = shutil.which("git")
    if not git:
        print("未发现 Git 命令，无法分析提交历史。", file=sys.stderr)
        return 1
    git_info = inspect_git(project)
    if not git_info.get("repository"):
        print("当前目录不是 Git 仓库；版本演进依赖提交历史。", file=sys.stderr)
        return 2

    try:
        source = detect_version_source(project)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    creating = source is None
    current_version = source["version"] if source else "0.1"
    groups: dict[str, list[str]] = {"major": [], "minor": [], "patch": [], "unknown": []}
    tag = None
    forced_reason = None
    if creating:
        planned_version = "0.1"
    else:
        try:
            subjects, tag = commits_since_version_tag(project, current_version)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        groups = classify_commit_subjects(subjects)
        change_level = highest_change_level(groups)
        if forced_reason:
            change_level = "major"
        planned_version = compute_next_version(current_version, change_level) if any(groups.values()) else current_version

    if not args.apply:
        plan = {
            "mode": "dry-run",
            "level": state.get("level"),
            "version_source": None if creating else {"file": source["path"].name, "kind": source["kind"]},
            "current_version": None if creating else current_version,
            "create_version_file": creating,
            "change_level": "major" if forced_reason else (None if creating or not any(groups.values()) else highest_change_level(groups)),
            "forced_reason": forced_reason,
            "since_tag": None if creating else tag,
            "commits": {} if creating else groups,
            "new_version": planned_version,
            "changelog_will_update": (creating or any(groups.values())) and (project / "CHANGELOG.md").is_file(),
            "commit_subject": f"chore(release): v{planned_version}" if creating or any(groups.values()) else None,
        }
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    if state.get("status") not in {"in_progress", "completed"} or state.get("gate") or state.get("execution_policy") != "AUTO":
        print("当前状态、Gate 或策略不允许应用版本变更。", file=sys.stderr)
        return 2
    code, staged_before = _git_output(project, "diff", "--cached", "--name-only")
    if code or staged_before:
        print("暂存区已有内容或无法检查；未修改版本，请先处理已有暂存。", file=sys.stderr)
        return 2
    targets = [source["path"].name] if source else ["VERSION"]
    code, dirty_targets = _git_output(project, "diff", "--name-only", "--", *targets, "CHANGELOG.md")
    if code or dirty_targets:
        print("版本源或 CHANGELOG 存在未提交修改；未应用版本变更。", file=sys.stderr)
        return 2
    if not _verifications_passed(state, git_info):
        print("尚无完整通过的验证证据；未验证不发布。", file=sys.stderr)
        return 2
    if not creating and not any(groups.values()):
        print("版本基线之后没有新提交；未更新版本。")
        return 0
    if (project / "CHANGELOG.md").is_symlink():
        print("CHANGELOG 不能是符号链接。", file=sys.stderr)
        return 2
    if creating:
        version_path = project / "VERSION"
        version_path.write_text(planned_version + "\n", encoding="utf-8")
        source = {"path": version_path, "kind": "version_file", "version": planned_version}
    else:
        try:
            write_version_to_source(source, planned_version)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    staged = [source["path"].relative_to(project).as_posix()]
    changelog = project / "CHANGELOG.md"
    if changelog.is_file():
        update_project_changelog(changelog, planned_version, groups)
        staged.append("CHANGELOG.md")
    add_result = subprocess.run(
        [git, "add", "--", *staged], cwd=project, capture_output=True, text=True
    )
    if add_result.returncode != 0:
        print(
            "暂存版本文件失败：\n" + (add_result.stderr or add_result.stdout).strip(),
            file=sys.stderr,
        )
        return 1
    subject = args.message or f"chore(release): v{planned_version}"
    body_lines = [
        f"{group_name}: {item}"
        for group_name in ("minor", "major", "patch", "unknown")
        for item in (groups.get(group_name) or [])
    ]
    commit_arguments = [git, "commit", "-m", subject]
    if body_lines:
        commit_arguments += ["-m", "\n".join(body_lines[:20])]
    commit_arguments += ["--only", "--", *staged]
    commit_result = subprocess.run(
        commit_arguments, cwd=project, capture_output=True, text=True
    )
    if commit_result.returncode != 0:
        print(
            "发布提交失败；版本文件及暂存内容已保留，请检查后恢复或继续，勿重复 apply：\n" + (commit_result.stderr or commit_result.stdout).strip(),
            file=sys.stderr,
        )
        return 1
    previous = "(新建)" if creating else current_version
    print(f"已更新版本 {previous} → {planned_version}，并创建发布提交。")
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
        "package-files.json",
        "scripts/workflow.py",
        "references/release-versioning.md",
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
    manifest_path = root / "package-files.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            items = manifest.get("items")
            if manifest.get("version") != 1 or not isinstance(items, list) or not items:
                raise ValueError("安装清单必须包含 version=1 和非空 items")
            if any(not isinstance(item, str) or not item or Path(item).name != item or item in {".", ".."}
                   or _is_absolute_file_path(item) for item in items) or len(items) != len(set(items)):
                raise ValueError("安装清单必须是唯一的包内顶层路径")
            for item in items:
                if not (root / item).exists() or (root / item).is_symlink():
                    raise ValueError(f"安装项不存在或为符号链接：{item}")
            for item in required:
                if Path(item).parts[0] not in items:
                    raise ValueError(f"安装清单遗漏运行时文件：{item}")
        except (ValueError, OSError) as exc:
            errors.append(str(exc))
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
    if schema.get("x-current-workflow-version") != version:
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

    verify_parser = subparsers.add_parser("verify", help="执行验证并绑定当前任务与文件指纹")
    verify_parser.add_argument("--project", required=True)
    verify_parser.add_argument("command", nargs=argparse.REMAINDER)
    verify_parser.set_defaults(handler=command_verify)

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

    version_parser = subparsers.add_parser(
        "version-bump", help="按改动分级计算并更新项目版本号（默认 dry-run）"
    )
    version_parser.add_argument("--project", required=True)
    version_parser.add_argument(
        "--apply", action="store_true", help="应用版本更新并创建发布提交；缺省只展示计划"
    )
    version_parser.add_argument("--message", help="覆盖默认发布提交主题 chore(release): v<版本>")
    version_parser.set_defaults(handler=command_version_bump)

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
