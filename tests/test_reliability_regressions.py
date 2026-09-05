import argparse
import contextlib
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import workflow as w
import test_version_bump as versions
import test_git_policy as policy


class ReliabilityRegressionTests(unittest.TestCase):
    def test_no_new_commits_dry_run_does_not_propose_a_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.prepare(directory)
            versions.run_git(root, "tag", "-f", "v1.2.3")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = w.command_version_bump(argparse.Namespace(project=str(root), apply=False, message=None))
            plan = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(plan["new_version"], "1.2.3")
            self.assertIsNone(plan["change_level"])
            self.assertIsNone(plan["commit_subject"])
            self.assertFalse(plan["changelog_will_update"])

    def test_invalid_task_timestamp_stage_and_boolean_level_rejected(self):
        state = w.build_initial_state(Path.cwd(), 1)
        for key, value in (("current_task", "broken"), ("updated_at", "yesterday"), ("stage", ""), ("level", True)):
            with self.subTest(key=key):
                invalid = dict(state, **{key: value})
                self.assertTrue(w.validate_state(invalid, Path.cwd()))

    def test_parent_path_escape_rejected(self):
        state = w.build_initial_state(Path.cwd(), 1)
        state["current_task"] = {"paths": ["../another-project"]}
        self.assertTrue(w.validate_state(state, Path.cwd()))

    def test_blocked_manual_and_gate_cannot_commit(self):
        for field, value in (("status", "blocked"), ("execution_policy", "MANUAL_ONLY"), ("gate", "review")):
            state = policy.ready_state()
            state[field] = value
            self.assertFalse(w.evaluate_git_action("local_commit", state, policy.ready_git())["allowed"])

    def test_stale_task_content_and_unbound_evidence_rejected(self):
        for change in ("task", "content", "legacy"):
            state = policy.ready_state()
            git = policy.ready_git()
            if change == "task":
                state["current_task"]["title"] = "another task"
            elif change == "content":
                git["fingerprint"] = "changed-content"
            else:
                state["verifications"] = [{"status": "passed"}]
            self.assertFalse(w.evaluate_git_action("local_commit", state, git)["allowed"])

    def test_current_failure_blocks_even_with_another_pass(self):
        state = policy.ready_state()
        failed = dict(state["verifications"][0], command="other", status="failed", exit_code=1)
        state["verifications"].append(failed)
        self.assertFalse(w.evaluate_git_action("local_commit", state, policy.ready_git())["allowed"])

    def test_clean_committed_branch_can_reach_remote_approval(self):
        state = policy.ready_state()
        state["permissions"]["allow_push_own_branch"] = True
        git = dict(policy.ready_git(), changed_files=[])
        decision = w.evaluate_git_action("push_own_branch", state, git)
        self.assertFalse(decision["allowed"])
        self.assertTrue(decision["requires_gate"])

    def test_json_version_does_not_change_earlier_dependency_or_nested_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = '{"dependencies":{"x":"1.2.3","nested":{"version":"1.2.3"}}, "version": "1.2.3"}\n'
            path = root / "package.json"
            path.write_text(text)
            w.write_version_to_source(w.detect_version_source(root), "1.2.4")
            expected = text.replace('}, "version": "1.2.3"', '}, "version": "1.2.4"')
            self.assertEqual(path.read_text(), expected)

    def test_toml_only_updates_project_section(self):
        for name, section in (("pyproject.toml", "project"), ("Cargo.toml", "package")):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = root / name
                original = '[tool.example]\nversion = "1.2.3"\n[' + section + ']\nversion = "1.2.3" # preserve\n'
                path.write_text(original)
                w.write_version_to_source(w.detect_version_source(root), "1.2.4")
                self.assertEqual(path.read_text(), original.replace('version = "1.2.3" # preserve', 'version = "1.2.4" # preserve'))

    def test_invalid_and_ambiguous_manifest_rejected(self):
        with self.assertRaises(ValueError):
            w._manifest_version('{"version":"1.0","version":"2.0"}', "package_json")
        with self.assertRaises(ValueError):
            w._manifest_version('[project]\nversion="1.0"\n[tool.poetry]\nversion="2.0"', "pyproject.toml")

    def prepare(self, directory):
        return versions.VersionBumpCommandTests().prepare_project(directory)

    def test_existing_index_refused_without_any_file_or_index_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.prepare(directory)
            note = root / "user.txt"
            note.write_text("user staged content")
            versions.run_git(root, "add", "user.txt")
            before_index = subprocess.check_output(["git", "diff", "--cached"], cwd=root)
            before = (root / "VERSION").read_bytes()
            result = w.command_version_bump(argparse.Namespace(project=str(root), apply=True, message=None))
            self.assertEqual(result, 2)
            self.assertEqual((root / "VERSION").read_bytes(), before)
            self.assertEqual(subprocess.check_output(["git", "diff", "--cached"], cwd=root), before_index)

    def test_breaking_change_in_commit_body_is_classified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.prepare(directory)
            versions.run_git(root, "commit", "--allow-empty", "-m", "fix: endpoint", "-m", "BREAKING CHANGE: removed old response")
            commits, baseline = w.commits_since_version_tag(root, "1.2.3")
            self.assertEqual(baseline, "v1.2.3")
            self.assertEqual(w.highest_change_level(w.classify_commit_subjects(commits)), "major")

    def test_release_commit_is_next_baseline_without_tag(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.prepare(directory)
            with mock.patch.dict(os.environ, versions.IDENTITY_ENV):
                self.assertEqual(w.command_version_bump(argparse.Namespace(project=str(root), apply=True, message=None)), 0)
            versions.run_git(root, "commit", "--allow-empty", "-m", "fix: next version")
            commits, baseline = w.commits_since_version_tag(root, "1.3.0")
            self.assertEqual(commits, ["fix: next version"])
            self.assertRegex(baseline, r"^[0-9a-f]{40}$")

    def test_risk_does_not_force_breaking_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.prepare(directory)
            state = versions.write_state(root)
            state["risk"] = "R3"
            (root / ".elx-level/state.json").write_text(json.dumps(state))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = w.command_version_bump(argparse.Namespace(project=str(root), apply=False, message=None))
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["change_level"], "minor")

    def test_verify_records_real_exit_and_invalidates_changed_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.prepare(directory)
            args = argparse.Namespace(project=str(root), command=[sys.executable, "-c", "print('verified')"])
            self.assertEqual(w.command_verify(args), 0)
            state = json.loads((root / ".elx-level/state.json").read_text())
            self.assertTrue(w._verifications_passed(state, w.inspect_git(root)))
            (root / "src/app.py").write_text("changed")
            self.assertFalse(w._verifications_passed(state, w.inspect_git(root)))
            args.command = [sys.executable, "-c", "raise SystemExit(4)"]
            self.assertEqual(w.command_verify(args), 1)
            state = json.loads((root / ".elx-level/state.json").read_text())
            self.assertFalse(w._verifications_passed(state, w.inspect_git(root)))
            self.assertEqual(state["verifications"][-1]["exit_code"], 4)
            self.assertEqual(state["verifications"][-1]["status"], "failed")

    def test_verify_does_not_pass_a_command_that_changes_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.prepare(directory)
            args = argparse.Namespace(project=str(root), command=[sys.executable, "-c", "from pathlib import Path; Path('new.txt').write_text('new')"])
            self.assertEqual(w.command_verify(args), 1)
            state = json.loads((root / ".elx-level/state.json").read_text())
            self.assertFalse(w._verifications_passed(state, w.inspect_git(root)))

    def test_migration_repeat_preserves_legacy_bytes_and_detects_changed_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = w.build_initial_state(root, 1)
            legacy = root / ".project-workflow"
            legacy.mkdir()
            source = legacy / "state.json"
            source.write_text(json.dumps(state))
            before = source.read_bytes()
            args = argparse.Namespace(project=str(root), target_level=None, approved_by=None, reason=None)
            self.assertEqual(w.command_migrate(args), 0)
            self.assertEqual(w.command_migrate(args), 0)
            self.assertEqual(w.command_validate(args), 0)
            self.assertEqual(source.read_bytes(), before)
            source.write_text(json.dumps(dict(state, stage="changed")))
            self.assertNotEqual(w.command_validate(args), 0)
            self.assertNotEqual(w.command_migrate(args), 0)

    def test_generated_adapter_command_runs_from_target_project(self):
        import shlex
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            w.command_init(argparse.Namespace(project=str(root), level=1, force=False))
            args = argparse.Namespace(project=str(root), platform="codex")
            self.assertEqual(w.command_render_adapter(args), 0)
            text = (root / "AGENTS.md").read_text(encoding="utf-8")
            line = next(line for line in text.splitlines() if "状态校验：" in line)
            argv = shlex.split(line.split('`')[1])
            result = subprocess.run([sys.executable, *argv[1:]], cwd=root, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_chinese_and_renamed_paths_are_read_without_git_quoting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.prepare(directory)
            (root / "中文文件.txt").write_text("ok")
            self.assertIn("中文文件.txt", w.inspect_git(root)["changed_files"])
            versions.run_git(root, "mv", "src/app.py", "src/renamed.py")
            info = w.inspect_git(root)
            self.assertIn("src/app.py", info["changed_files"])
            self.assertIn("src/renamed.py", info["changed_files"])

    def test_invalid_legacy_migration_does_not_create_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / ".project-workflow"
            legacy.mkdir()
            state = w.build_initial_state(root, 1)
            state.update(schema_version="1.1.0", workflow_version="0.4.0", current_task="broken")
            (legacy / "state.json").write_text(json.dumps(state))
            args = argparse.Namespace(project=str(root), target_level=None, approved_by=None, reason=None)
            self.assertNotEqual(w.command_migrate(args), 0)
            self.assertFalse((root / ".elx-level").exists())

    def test_dirty_tracked_manifest_refused_without_committing_user_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.prepare(directory)
            (root / "VERSION").write_text("1.2.4")
            versions.write_state(root)
            before = (root / "VERSION").read_bytes()
            args = argparse.Namespace(project=str(root), apply=True, message=None)
            self.assertEqual(w.command_version_bump(args), 2)
            self.assertEqual((root / "VERSION").read_bytes(), before)

    def test_future_workflow_version_rejected_without_downgrade(self):
        state = w.build_initial_state(Path.cwd(), 1)
        state["workflow_version"] = "99.0"
        self.assertTrue(w.validate_state(state, Path.cwd()))

    def test_level4_approved_execution_can_be_auto_with_low_risk(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = w.build_initial_state(root, 4)
            state["gate"] = "level4-execution-review"
            state["status"] = "waiting_approval"
            (root / ".elx-level").mkdir()
            (root / ".elx-level/state.json").write_text(json.dumps(state))
            args = argparse.Namespace(project=str(root), approve_gate="level4-execution-review", to_stage="implementation", approved_by="owner", next_gate=None)
            self.assertEqual(w.command_transition(args), 0)
            self.assertEqual(json.loads((root / ".elx-level/state.json").read_text())["execution_policy"], "AUTO")

    def test_installed_relative_adapter_survives_project_move(self):
        import shlex
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "original"
            root.mkdir()
            package = root / ".codex/skills/elx-level"
            package.mkdir(parents=True)
            for name in ("adapters", "scripts", "schemas"):
                shutil.copytree(w.PACKAGE_ROOT / name, package / name)
            shutil.copy2(w.PACKAGE_ROOT / "VERSION", package / "VERSION")
            w.command_init(argparse.Namespace(project=str(root), level=1, force=False))
            with mock.patch.object(w, "PACKAGE_ROOT", package):
                w.command_render_adapter(argparse.Namespace(project=str(root), platform="codex"))
            moved = parent / "moved"
            root.rename(moved)
            line = next(line for line in (moved / "AGENTS.md").read_text(encoding="utf-8").splitlines() if "状态校验：" in line)
            command = shlex.split(line.split('`')[1])
            self.assertEqual(command[1], ".codex/skills/elx-level/scripts/workflow.py")
            result = subprocess.run([sys.executable, *command[1:]], cwd=moved, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(Path("C:/Program Files/Git/bin/bash.exe").is_file(), "requires Git Bash on Windows")
    def test_posix_installer_produces_valid_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrappers = root / "bin"
            wrappers.mkdir()
            python = Path(sys.executable).as_posix()
            (wrappers / "python3").write_text('#!/usr/bin/env bash\nexec "' + python + '" "$@"\n', encoding="utf-8")
            project = root / "project"
            project.mkdir()
            env = {**os.environ, "PATH": str(wrappers) + os.pathsep + os.environ.get("PATH", "")}
            script = (w.PACKAGE_ROOT / "scripts/install.sh").as_posix()
            result = subprocess.run(["C:/Program Files/Git/bin/bash.exe", script, "--platform", "claude-code", "--scope", "project", "--project", project.as_posix()], env=env, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            installed = project / ".claude/skills/elx-level"
            self.assertEqual(w.validate_package(installed), [])

    def test_dynamic_version_source_is_not_guessed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text('[project]\ndynamic = ["version"]\n')
            with self.assertRaises(ValueError):
                w.detect_version_source(root)


if __name__ == "__main__":
    unittest.main()
