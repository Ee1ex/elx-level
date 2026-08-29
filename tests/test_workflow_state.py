import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "workflow.py"
PUBLIC_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def write_legacy_state(project: Path, level: int = 1) -> Path:
    result = run_cli("init", "--project", str(project), "--level", str(level))
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    current = project / ".elx-level"
    legacy = project / ".project-workflow"
    if current.exists():
        current.rename(legacy)
    state_path = legacy / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["workflow_version"] = "1.0"
    state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return legacy


class WorkflowStateTests(unittest.TestCase):
    def test_init_uses_elx_level_state_and_docs_only(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            result = run_cli("init", "--project", temp, "--level", "1")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((project / ".elx-level" / "state.json").is_file())
            self.assertTrue((project / "docs" / "elx-level" / "STATUS.md").is_file())
            self.assertFalse((project / ".project-workflow").exists())

    def test_migrate_copies_legacy_state_without_mutating_source(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            legacy = write_legacy_state(project)
            before = {
                path.relative_to(legacy): path.read_bytes()
                for path in legacy.rglob("*")
                if path.is_file()
            }
            result = run_cli("migrate", "--project", temp)
            self.assertEqual(result.returncode, 0, result.stderr)
            current = project / ".elx-level"
            self.assertTrue((current / "state.json").is_file())
            after = {
                path.relative_to(legacy): path.read_bytes()
                for path in legacy.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, before)
            state = json.loads((current / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["workflow_version"], PUBLIC_VERSION)
            self.assertTrue((project / "docs" / "elx-level" / "STATUS.md").is_file())

    def test_migrate_stops_when_legacy_and_current_state_both_exist(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            self.assertEqual(run_cli("init", "--project", temp, "--level", "1").returncode, 0)
            current = project / ".elx-level"
            legacy = project / ".project-workflow"
            if current.exists():
                shutil.copytree(current, legacy)
            else:
                shutil.copytree(legacy, current)
            before = (current / "state.json").read_bytes()
            result = run_cli("migrate", "--project", temp)
            self.assertEqual(result.returncode, 2)
            self.assertIn("新旧状态目录同时存在", result.stderr)
            self.assertEqual((current / "state.json").read_bytes(), before)

    def test_validate_does_not_implicitly_copy_legacy_state(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            write_legacy_state(project)
            result = run_cli("validate", "--project", temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("migrate", result.stderr)
            self.assertFalse((project / ".elx-level").exists())

    def test_init_creates_state_backup_and_status(self):
        expected_stage = {
            1: "project-memory",
            2: "phase-0",
            3: "repository-intake",
            4: "requirements-analysis",
        }
        expected_policy = {1: "AUTO", 2: "AUTO", 3: "AUTO", 4: "CONFIRM"}
        for level in (1, 2, 3, 4):
            with self.subTest(level=level), tempfile.TemporaryDirectory() as temp:
                project = Path(temp)
                result = run_cli("init", "--project", temp, "--level", str(level))
                self.assertEqual(result.returncode, 0, result.stderr)
                state_path = project / ".elx-level" / "state.json"
                backup_path = project / ".elx-level" / "state.backup.json"
                status_path = project / "docs" / "elx-level" / "STATUS.md"
                self.assertTrue(state_path.is_file())
                self.assertTrue(backup_path.is_file())
                self.assertTrue(status_path.is_file())
                state = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertEqual(state["level"], level)
                self.assertEqual(state["stage"], expected_stage[level])
                self.assertEqual(state["execution_policy"], expected_policy[level])
                self.assertIsNone(state["gate"])
                self.assertFalse(state["permissions"]["allow_push_own_branch"])
                self.assertFalse(state["permissions"]["allow_create_draft_pr"])

    def test_validate_accepts_valid_state(self):
        for level in ("1", "2", "3", "4"):
            with self.subTest(level=level), tempfile.TemporaryDirectory() as temp:
                self.assertEqual(run_cli("init", "--project", temp, "--level", level).returncode, 0)
                result = run_cli("validate", "--project", temp)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"LEVEL {level}", result.stdout)

    def test_validate_rejects_missing_field_invalid_level_and_absolute_path(self):
        cases = [
            lambda state: state.pop("stage"),
            lambda state: state.__setitem__("level", 9),
            lambda state: state.__setitem__("artifacts", [{"path": "C:\\private\\file.md"}]),
        ]
        for mutate in cases:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as temp:
                self.assertEqual(run_cli("init", "--project", temp, "--level", "1").returncode, 0)
                state_path = Path(temp) / ".elx-level" / "state.json"
                state = json.loads(state_path.read_text(encoding="utf-8"))
                mutate(state)
                state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
                result = run_cli("validate", "--project", temp)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("状态无效", result.stderr)

    def test_init_does_not_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            self.assertEqual(run_cli("init", "--project", temp, "--level", "1").returncode, 0)
            state_path = project / ".elx-level" / "state.json"
            original = json.loads(state_path.read_text(encoding="utf-8"))
            original["project_id"] = "keep-me"
            state_path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
            blocked = run_cli("init", "--project", temp, "--level", "2")
            self.assertEqual(blocked.returncode, 2)
            self.assertEqual(json.loads(state_path.read_text(encoding="utf-8"))["project_id"], "keep-me")
            forced = run_cli("init", "--project", temp, "--level", "2", "--force")
            self.assertEqual(forced.returncode, 0, forced.stderr)
            backup = json.loads(
                (project / ".elx-level" / "state.backup.json").read_text(encoding="utf-8")
            )
            self.assertEqual(backup["project_id"], "keep-me")
            self.assertEqual(json.loads(state_path.read_text(encoding="utf-8"))["level"], 2)

    def test_status_renders_level_aware_policy_and_gate_sections(self):
        for level in (1, 2, 3):
            with self.subTest(level=level), tempfile.TemporaryDirectory() as temp:
                self.assertEqual(
                    run_cli("init", "--project", temp, "--level", str(level)).returncode,
                    0,
                )
                result = run_cli("status", "--project", temp)
                self.assertEqual(result.returncode, 0, result.stderr)
                status = (Path(temp) / "docs" / "elx-level" / "STATUS.md").read_text(
                    encoding="utf-8"
                )
                self.assertIn("执行策略：AUTO", status)
                self.assertNotIn("## 当前人工 Gate", status)
                self.assertNotIn("## 当前风险与未决事项", status)

        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(run_cli("init", "--project", temp, "--level", "4").returncode, 0)
            result = run_cli("status", "--project", temp)
            self.assertEqual(result.returncode, 0, result.stderr)
            status = (Path(temp) / "docs" / "elx-level" / "STATUS.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("执行策略：CONFIRM", status)
            self.assertIn("## 当前风险与未决事项", status)
            self.assertIn("## 当前人工 Gate", status)

    def test_validate_does_not_mutate_older_workflow_version(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(run_cli("init", "--project", temp, "--level", "1").returncode, 0)
            state_path = Path(temp) / ".elx-level" / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["workflow_version"] = "0.3.0"
            state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            before = state_path.read_bytes()
            result = run_cli("validate", "--project", temp)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(state_path.read_bytes(), before)

    def test_status_refreshes_workflow_version_with_backup_and_history(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(run_cli("init", "--project", temp, "--level", "2").returncode, 0)
            project = Path(temp)
            state_path = project / ".elx-level" / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["workflow_version"] = "0.3.0"
            state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            result = run_cli("status", "--project", temp)
            self.assertEqual(result.returncode, 0, result.stderr)
            current = json.loads(state_path.read_text(encoding="utf-8"))
            backup = json.loads(
                (project / ".elx-level" / "state.backup.json").read_text(encoding="utf-8")
            )
            self.assertEqual(current["workflow_version"], PUBLIC_VERSION)
            self.assertEqual(backup["workflow_version"], "0.3.0")
            event = next(
                item for item in current["history"] if item.get("event") == "workflow_version_updated"
            )
            self.assertEqual(event["from_version"], "0.3.0")
            self.assertEqual(event["to_version"], PUBLIC_VERSION)

    def test_transition_requires_matching_gate_and_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            self.assertEqual(run_cli("init", "--project", temp, "--level", "1").returncode, 0)
            state_path = project / ".elx-level" / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["gate"] = "scope-confirmation"
            state["status"] = "waiting_approval"
            state["execution_policy"] = "CONFIRM"
            state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            mismatch = run_cli(
                "transition",
                "--project",
                temp,
                "--approve-gate",
                "wrong-gate",
                "--to-stage",
                "requirements",
                "--approved-by",
                "owner",
            )
            self.assertEqual(mismatch.returncode, 2)
            success = run_cli(
                "transition",
                "--project",
                temp,
                "--approve-gate",
                "scope-confirmation",
                "--to-stage",
                "requirements",
                "--approved-by",
                "owner",
            )
            self.assertEqual(success.returncode, 0, success.stderr)
            state = json.loads(
                (project / ".elx-level" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["stage"], "requirements")
            self.assertIsNone(state["gate"])
            self.assertEqual(state["execution_policy"], "AUTO")
            self.assertEqual(state["history"][-1]["approved_by"], "owner")

    def test_migrate_supported_state_and_rejects_future_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            self.assertEqual(run_cli("init", "--project", temp, "--level", "1").returncode, 0)
            state_path = project / ".elx-level" / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["schema_version"] = "0.9.0"
            state.pop("permissions")
            state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            migrated = run_cli("migrate", "--project", temp)
            self.assertEqual(migrated.returncode, 0, migrated.stderr)
            current = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(current["schema_version"], "2.0")
            self.assertEqual(current["level"], 1)
            self.assertFalse(current["permissions"]["allow_push_own_branch"])
            self.assertEqual(current["status"], "waiting_approval")
            self.assertEqual(current["gate"], "level-migration-review")
            backup = json.loads(
                (project / ".elx-level" / "state.backup.json").read_text(encoding="utf-8")
            )
            self.assertEqual(backup["schema_version"], "0.9.0")
            self.assertEqual(backup["level"], 1)
            status = (project / "docs" / "elx-level" / "STATUS.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("旧 LEVEL", status)
            self.assertIn("新 LEVEL", status)
            self.assertIn("迁移原因", status)
            current["schema_version"] = "9.0.0"
            state_path.write_text(json.dumps(current, ensure_ascii=False), encoding="utf-8")
            rejected = run_cli("migrate", "--project", temp)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("不支持", rejected.stderr)

    def test_migrate_maps_legacy_levels_to_new_semantics(self):
        expected = {1: 1, 2: 3, 3: 4}
        for old_level, new_level in expected.items():
            with self.subTest(old_level=old_level), tempfile.TemporaryDirectory() as temp:
                self.assertEqual(run_cli("init", "--project", temp, "--level", "1").returncode, 0)
                state_path = Path(temp) / ".elx-level" / "state.json"
                state = json.loads(state_path.read_text(encoding="utf-8"))
                state["schema_version"] = "1.0.0"
                state["level"] = old_level
                state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
                migrated = run_cli("migrate", "--project", temp)
                self.assertEqual(migrated.returncode, 0, migrated.stderr)
                current = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertEqual(current["level"], new_level)
                self.assertEqual(current["gate"], "level-migration-review")
                self.assertEqual(current["status"], "waiting_approval")

    def test_legacy_level_three_can_be_reconfirmed_as_new_level_two(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(run_cli("init", "--project", temp, "--level", "1").returncode, 0)
            state_path = Path(temp) / ".elx-level" / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["schema_version"] = "1.0.0"
            state["level"] = 3
            state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            migrated = run_cli(
                "migrate",
                "--project",
                temp,
                "--target-level",
                "2",
                "--approved-by",
                "owner",
                "--reason",
                "确认自有线上产品责任模式并采用完整 PVS",
            )
            self.assertEqual(migrated.returncode, 0, migrated.stderr)
            current = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(current["level"], 2)
            self.assertEqual(current["status"], "waiting_approval")
            self.assertEqual(current["gate"], "level-migration-review")
            confirmation = current["history"][-1]
            self.assertEqual(confirmation["event"], "level_reconfirmed")
            self.assertEqual(confirmation["approved_by"], "owner")
            self.assertIn("完整 PVS", confirmation["reason"])

    def test_migrate_v040_level_four_preserves_analysis_and_requires_execution_review(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(run_cli("init", "--project", temp, "--level", "4").returncode, 0)
            state_path = Path(temp) / ".elx-level" / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["schema_version"] = "1.1.0"
            state["workflow_version"] = "0.4.0"
            state["level"] = 4
            state["stage"] = "requirements-analysis"
            state["gate"] = None
            state["status"] = "in_progress"
            state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

            migrated = run_cli("migrate", "--project", temp)
            self.assertEqual(migrated.returncode, 0, migrated.stderr)
            current = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(current["schema_version"], "2.0")
            self.assertEqual(current["workflow_version"], PUBLIC_VERSION)
            self.assertEqual(current["level"], 4)
            self.assertEqual(current["stage"], "requirements-analysis")
            self.assertEqual(current["gate"], "level4-execution-review")
            self.assertEqual(current["status"], "waiting_approval")

    def test_migrate_v040_levels_one_to_three_preserves_level_without_review_gate(self):
        for level in (1, 2, 3):
            with self.subTest(level=level), tempfile.TemporaryDirectory() as temp:
                self.assertEqual(
                    run_cli("init", "--project", temp, "--level", str(level)).returncode,
                    0,
                )
                state_path = Path(temp) / ".elx-level" / "state.json"
                state = json.loads(state_path.read_text(encoding="utf-8"))
                state["schema_version"] = "1.1.0"
                state["workflow_version"] = "0.4.0"
                state["level"] = level
                state["gate"] = None
                state["status"] = "in_progress"
                state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

                migrated = run_cli("migrate", "--project", temp)
                self.assertEqual(migrated.returncode, 0, migrated.stderr)
                current = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertEqual(current["schema_version"], "2.0")
                self.assertEqual(current["workflow_version"], PUBLIC_VERSION)
                self.assertEqual(current["level"], level)
                self.assertIsNone(current["gate"])
                self.assertEqual(current["status"], "in_progress")


if __name__ == "__main__":
    unittest.main()
