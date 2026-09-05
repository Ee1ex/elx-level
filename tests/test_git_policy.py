import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts import workflow


def ready_state() -> dict:
    state = {
        "risk": "R2",
        "status": "in_progress", "gate": None, "execution_policy": "AUTO",
        "permissions": {
            "allow_push_own_branch": False,
            "allow_create_draft_pr": False,
        },
        "current_task": {"title": "实现策略", "paths": ["src/policy.py"]},
        "verifications": [{"command": "python -m unittest", "status": "passed"}],
        "git": {"skill_created_branch": True},
    }

    state["verifications"][0].update({"task_id": workflow.task_identity(state), "fingerprint": "current-content",
                                       "exit_code": 0, "at": workflow.utc_now()})
    return state


def personal_state(level: int) -> dict:
    state = ready_state()
    state["level"] = level
    state["git"] = {"skill_created_branch": False}
    return state


def ready_git() -> dict:
    return {
        "available": True,
        "fingerprint": "current-content",
        "repository": True,
        "branch": "workflow/policy",
        "default_branch": "main",
        "changed_files": ["src/policy.py"],
        "changes_in_scope": True,
        "unrelated_changes": [],
        "remote_name": "origin",
        "remote_url": "https://github.com/example/project.git",
        "authenticated": True,
        "ahead_commits": 1,
    }


class GitPolicyTests(unittest.TestCase):
    def test_git_init_always_requires_an_explicit_gate(self) -> None:
        decision = workflow.evaluate_git_action(
            "git_init", ready_state(), {"available": True, "repository": False}
        )
        self.assertFalse(decision["allowed"])
        self.assertTrue(decision["requires_gate"])
        self.assertIn("Gate", " ".join(decision["reasons"]))

    def test_force_push_and_history_rewrite_are_always_forbidden(self) -> None:
        for action in ("force_push", "rewrite_history"):
            with self.subTest(action=action):
                decision = workflow.evaluate_git_action(action, ready_state(), ready_git())
                self.assertFalse(decision["allowed"])
                self.assertFalse(decision["requires_gate"])
                self.assertIn("禁止", " ".join(decision["reasons"]))

    def test_high_impact_remote_actions_route_to_github_approval(self) -> None:
        for action in ("delete_remote_branch", "ready_pr", "merge", "tag", "release"):
            with self.subTest(action=action):
                decision = workflow.evaluate_git_action(action, ready_state(), ready_git())
                self.assertFalse(decision["allowed"])
                self.assertTrue(decision["requires_gate"])
                reasons = " ".join(decision["reasons"])
                self.assertIn("GitHub 插件", reasons)
                self.assertIn("明确确认", reasons)

    def test_local_commit_requires_owned_branch_scope_and_verification(self) -> None:
        decision = workflow.evaluate_git_action("local_commit", ready_state(), ready_git())
        self.assertTrue(decision["allowed"])
        self.assertFalse(decision["requires_gate"])

        git_info = ready_git()
        git_info["unrelated_changes"] = ["notes/private.md"]
        denied = workflow.evaluate_git_action("local_commit", ready_state(), git_info)
        self.assertFalse(denied["allowed"])
        self.assertIn("无关修改", " ".join(denied["reasons"]))

    def test_level1_and_level2_commit_without_skill_created_branch(self) -> None:
        for level in (1, 2):
            with self.subTest(level=level):
                decision = workflow.evaluate_git_action(
                    "local_commit", personal_state(level), ready_git()
                )
                self.assertTrue(decision["allowed"])
                self.assertFalse(decision["requires_gate"])

    def test_level2_commits_on_default_branch_after_verification(self) -> None:
        git_info = ready_git()
        git_info["branch"] = "main"
        decision = workflow.evaluate_git_action("local_commit", personal_state(2), git_info)
        self.assertTrue(decision["allowed"])
        self.assertFalse(decision["requires_gate"])

    def test_level2_unverified_changes_stay_uncommitted(self) -> None:
        state = personal_state(2)
        state["verifications"] = [{"command": "python -m unittest", "status": "failed"}]
        decision = workflow.evaluate_git_action("local_commit", state, ready_git())
        self.assertFalse(decision["allowed"])
        self.assertIn("验证证据", " ".join(decision["reasons"]))

    def test_level3_still_requires_skill_owned_branch(self) -> None:
        decision = workflow.evaluate_git_action("local_commit", personal_state(3), ready_git())
        self.assertFalse(decision["allowed"])
        self.assertIn("不是本 Skill 创建", " ".join(decision["reasons"]))

    def test_level2_default_branch_push_stays_denied(self) -> None:
        state = personal_state(2)
        state["permissions"]["allow_push_own_branch"] = True
        git_info = ready_git()
        git_info["branch"] = "main"
        decision = workflow.evaluate_git_action("push_own_branch", state, git_info)
        self.assertFalse(decision["allowed"])
        self.assertIn("默认分支", " ".join(decision["reasons"]))

    def test_remote_writes_default_to_denied(self) -> None:
        state = ready_state()
        push = workflow.evaluate_git_action("push_own_branch", state, ready_git())
        draft = workflow.evaluate_git_action("create_draft_pr", state, ready_git())
        self.assertFalse(push["allowed"])
        self.assertFalse(draft["allowed"])
        self.assertIn("allow_push_own_branch", " ".join(push["reasons"]))
        self.assertIn("allow_create_draft_pr", " ".join(draft["reasons"]))

    def test_configured_remote_scope_still_requires_action_time_approval(self) -> None:
        state = ready_state()
        state["permissions"]["allow_push_own_branch"] = True
        state["permissions"]["allow_create_draft_pr"] = True
        for action in ("push_own_branch", "create_draft_pr"):
            decision = workflow.evaluate_git_action(action, state, ready_git())
            self.assertFalse(decision["allowed"])
            self.assertTrue(decision["requires_gate"])
            self.assertIn("GitHub 插件", " ".join(decision["reasons"]))

    def test_main_branch_remote_write_is_denied(self) -> None:
        state = ready_state()
        state["permissions"]["allow_push_own_branch"] = True
        git_info = ready_git()
        git_info["branch"] = "main"
        decision = workflow.evaluate_git_action("push_own_branch", state, git_info)
        self.assertFalse(decision["allowed"])
        self.assertIn("默认分支", " ".join(decision["reasons"]))

    @unittest.skipUnless(shutil.which("git"), "当前测试环境未发现 Git")
    def test_inspect_git_reads_branch_changes_and_remote(self) -> None:
        git = shutil.which("git")
        assert git
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run([git, "init"], cwd=project, check=True, capture_output=True)
            subprocess.run(
                [git, "config", "user.email", "workflow@example.invalid"],
                cwd=project,
                check=True,
            )
            subprocess.run(
                [git, "config", "user.name", "Workflow Test"], cwd=project, check=True
            )
            (project / "tracked.txt").write_text("base\n", encoding="utf-8")
            subprocess.run([git, "add", "tracked.txt"], cwd=project, check=True)
            subprocess.run([git, "commit", "-m", "base"], cwd=project, check=True, capture_output=True)
            subprocess.run([git, "checkout", "-b", "workflow/test"], cwd=project, check=True, capture_output=True)
            subprocess.run(
                [git, "remote", "add", "origin", "https://github.com/example/project.git"],
                cwd=project,
                check=True,
            )
            (project / "tracked.txt").write_text("changed\n", encoding="utf-8")

            info = workflow.inspect_git(project)
            self.assertTrue(info["repository"])
            self.assertEqual(info["branch"], "workflow/test")
            self.assertIn("tracked.txt", info["changed_files"])
            self.assertEqual(info["remote_name"], "origin")

    @unittest.skipUnless(shutil.which("git"), "当前测试环境未发现 Git")
    def test_git_init_requires_explicit_confirm_and_refuses_existing_repo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            args = argparse.Namespace(project=str(project), confirm=False, message="base")
            self.assertEqual(workflow.command_git_init(args), 2)
            self.assertFalse((project / ".git").exists())

            args.confirm = True
            self.assertEqual(workflow.command_git_init(args), 0)
            self.assertTrue((project / ".git").exists())

            self.assertEqual(workflow.command_git_init(args), 2)

    @unittest.skipUnless(shutil.which("git"), "当前测试环境未发现 Git")
    def test_git_init_commits_only_the_workflow_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            state_dir = project / ".elx-level"
            state_dir.mkdir()
            (state_dir / "state.json").write_text("{}\n", encoding="utf-8")
            docs_dir = project / "docs" / "elx-level"
            docs_dir.mkdir(parents=True)
            (docs_dir / "STATUS.md").write_text("# STATUS\n", encoding="utf-8")
            (project / "user-note.txt").write_text("keep untracked\n", encoding="utf-8")
            args = argparse.Namespace(
                project=str(project), confirm=True, message="chore: workflow baseline"
            )
            identity = {
                "GIT_AUTHOR_NAME": "Workflow Test",
                "GIT_AUTHOR_EMAIL": "workflow@example.invalid",
                "GIT_COMMITTER_NAME": "Workflow Test",
                "GIT_COMMITTER_EMAIL": "workflow@example.invalid",
            }
            with mock.patch.dict(os.environ, identity):
                self.assertEqual(workflow.command_git_init(args), 0)
            git = shutil.which("git")
            assert git
            listed = subprocess.run(
                [git, "ls-files"], cwd=project, capture_output=True, text=True, check=True
            ).stdout
            self.assertIn(".elx-level/state.json", listed)
            self.assertIn("docs/elx-level/STATUS.md", listed)
            self.assertNotIn("user-note.txt", listed)


if __name__ == "__main__":
    unittest.main()
