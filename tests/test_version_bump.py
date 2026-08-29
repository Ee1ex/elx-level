import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import workflow


IDENTITY_ENV = {
    "GIT_AUTHOR_NAME": "Workflow Test",
    "GIT_AUTHOR_EMAIL": "workflow@example.invalid",
    "GIT_COMMITTER_NAME": "Workflow Test",
    "GIT_COMMITTER_EMAIL": "workflow@example.invalid",
}


def write_state(project: Path, level: int = 1, verifications: list | None = None) -> dict:
    state = workflow.build_initial_state(project, level)
    state["verifications"] = (
        [{"command": "python -m unittest", "status": "passed"}]
        if verifications is None
        else verifications
    )
    state_dir = project / ".elx-level"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return state


def run_git(project: Path, *arguments: str) -> None:
    git = shutil.which("git")
    assert git
    subprocess.run(
        [git, *arguments],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **IDENTITY_ENV},
    )


class ComputeNextVersionTests(unittest.TestCase):
    def test_three_segment_mapping(self) -> None:
        self.assertEqual(workflow.compute_next_version("1.2.3", "major"), "2.0.0")
        self.assertEqual(workflow.compute_next_version("1.2.3", "minor"), "1.3.0")
        self.assertEqual(workflow.compute_next_version("1.2.3", "patch"), "1.2.4")

    def test_two_segment_mapping(self) -> None:
        self.assertEqual(workflow.compute_next_version("0.1", "major"), "1.0")
        self.assertEqual(workflow.compute_next_version("0.1", "minor"), "0.2")
        self.assertEqual(workflow.compute_next_version("0.1", "patch"), "0.2")

    def test_prerelease_suffix_is_preserved(self) -> None:
        self.assertEqual(workflow.compute_next_version("1.2.3-beta.1", "minor"), "1.3.0-beta.1")
        self.assertEqual(workflow.compute_next_version("0.1-rc", "patch"), "0.2-rc")

    def test_invalid_versions_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            workflow.compute_next_version("abc", "minor")
        with self.assertRaises(ValueError):
            workflow.compute_next_version("1.2.3.4", "minor")


class ClassificationTests(unittest.TestCase):
    def test_breaking_and_conventional_prefixes(self) -> None:
        groups = workflow.classify_commit_subjects(
            [
                "feat!: redesign public api",
                "fix(parser): handle empty input",
                "feat: add export",
                "docs: update readme",
                "random commit without prefix",
                "chore: bump deps",
            ]
        )
        self.assertEqual(groups["major"], ["feat!: redesign public api"])
        self.assertEqual(groups["minor"], ["feat: add export"])
        self.assertEqual(
            groups["patch"],
            ["fix(parser): handle empty input", "docs: update readme", "chore: bump deps"],
        )
        self.assertEqual(groups["unknown"], ["random commit without prefix"])
        self.assertEqual(workflow.highest_change_level(groups), "major")

    def test_breaking_change_footnote_forces_major(self) -> None:
        groups = workflow.classify_commit_subjects(["fix: data migration with BREAKING CHANGE note"])
        self.assertEqual(groups["major"], ["fix: data migration with BREAKING CHANGE note"])

    def test_minor_wins_over_patch(self) -> None:
        groups = workflow.classify_commit_subjects(["fix: a", "feat: b"])
        self.assertEqual(workflow.highest_change_level(groups), "minor")


class VersionSourceTests(unittest.TestCase):
    def test_returns_none_without_any_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(workflow.detect_version_source(Path(directory)))

    def test_prefers_version_file_over_package_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "package.json").write_text(
                '{"name":"x","version":"1.2.3"}', encoding="utf-8"
            )
            (project / "VERSION").write_text("0.1\n", encoding="utf-8")
            source = workflow.detect_version_source(project)
            self.assertEqual(source["kind"], "version_file")
            self.assertEqual(source["version"], "0.1")

    def test_reads_package_json_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "package.json").write_text(
                '{"name":"x","version":"1.2.3"}', encoding="utf-8"
            )
            source = workflow.detect_version_source(project)
            self.assertEqual(source["kind"], "package_json")
            self.assertEqual(source["version"], "1.2.3")

    def test_reads_toml_versions(self) -> None:
        for name in ("pyproject.toml", "Cargo.toml"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                (project / name).write_text(
                    f'[package]\nname = "x"\nversion = "0.3.1"\n', encoding="utf-8"
                )
                source = workflow.detect_version_source(project)
                self.assertEqual(source["kind"], name)
                self.assertEqual(source["version"], "0.3.1")


@unittest.skipUnless(shutil.which("git"), "当前测试环境未发现 Git")
class VersionBumpCommandTests(unittest.TestCase):
    def prepare_project(self, directory: str) -> Path:
        project = Path(directory)
        (project / "VERSION").write_text("1.2.3\n", encoding="utf-8")
        run_git(project, "init")
        run_git(project, "add", "VERSION")
        run_git(project, "commit", "-m", "chore: baseline")
        run_git(project, "tag", "v1.2.3")
        source_dir = project / "src"
        source_dir.mkdir()
        (source_dir / "app.py").write_text("print('hi')\n", encoding="utf-8")
        run_git(project, "add", "src/app.py")
        run_git(project, "commit", "-m", "feat: add export")
        (source_dir / "app.py").write_text("print('hello')\n", encoding="utf-8")
        run_git(project, "add", "src/app.py")
        run_git(project, "commit", "-m", "fix(parser): handle empty input")
        write_state(project, level=1)
        return project

    def test_dry_run_reports_plan_without_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.prepare_project(directory)
            args = argparse.Namespace(project=str(project), apply=False, message=None)
            buffer = io.StringIO()
            with mock.patch.dict(os.environ, IDENTITY_ENV), contextlib.redirect_stdout(buffer):
                exit_code = workflow.command_version_bump(args)
            self.assertEqual(exit_code, 0)
            plan = json.loads(buffer.getvalue())
            self.assertEqual(plan["current_version"], "1.2.3")
            self.assertEqual(plan["since_tag"], "v1.2.3")
            self.assertEqual(plan["change_level"], "minor")
            self.assertEqual(plan["new_version"], "1.3.0")
            self.assertIn("feat: add export", plan["commits"]["minor"])
            self.assertFalse(plan["create_version_file"])
            self.assertEqual((project / "VERSION").read_text(encoding="utf-8").strip(), "1.2.3")

    def test_apply_updates_version_changelog_and_creates_release_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.prepare_project(directory)
            (project / "CHANGELOG.md").write_text(
                "# Changelog\n\n## [1.2.3] - 2026-01-01\n\n- old entry\n", encoding="utf-8"
            )
            args = argparse.Namespace(project=str(project), apply=True, message=None)
            with mock.patch.dict(os.environ, IDENTITY_ENV):
                exit_code = workflow.command_version_bump(args)
            self.assertEqual(exit_code, 0)
            self.assertEqual((project / "VERSION").read_text(encoding="utf-8").strip(), "1.3.0")
            changelog = (project / "CHANGELOG.md").read_text(encoding="utf-8")
            self.assertIn("## [1.3.0]", changelog)
            self.assertIn("- feat: add export", changelog)
            self.assertIn("- fix(parser): handle empty input", changelog)
            self.assertLess(changelog.index("## [1.3.0]"), changelog.index("## [1.2.3]"))
            log = subprocess.run(
                [shutil.which("git"), "log", "-1", "--pretty=%s"],
                cwd=project,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(log, "chore(release): v1.3.0")
            listed = subprocess.run(
                [shutil.which("git"), "show", "--pretty=", "--name-only", "HEAD"],
                cwd=project,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            self.assertIn("VERSION", listed)
            self.assertIn("CHANGELOG.md", listed)
            self.assertNotIn("src/app.py", listed)

    def test_apply_without_passed_verifications_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.prepare_project(directory)
            write_state(project, level=1, verifications=[{"command": "x", "status": "failed"}])
            args = argparse.Namespace(project=str(project), apply=True, message=None)
            with mock.patch.dict(os.environ, IDENTITY_ENV):
                exit_code = workflow.command_version_bump(args)
            self.assertEqual(exit_code, 2)
            self.assertEqual((project / "VERSION").read_text(encoding="utf-8").strip(), "1.2.3")

    def test_level3_projects_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.prepare_project(directory)
            write_state(project, level=3)
            args = argparse.Namespace(project=str(project), apply=False, message=None)
            with mock.patch.dict(os.environ, IDENTITY_ENV):
                exit_code = workflow.command_version_bump(args)
            self.assertEqual(exit_code, 2)

    def test_missing_version_source_creates_file_on_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            run_git(project, "init")
            readme = project / "README.md"
            readme.write_text("# demo\n", encoding="utf-8")
            run_git(project, "add", "README.md")
            run_git(project, "commit", "-m", "docs: init")
            write_state(project, level=2)
            args = argparse.Namespace(project=str(project), apply=True, message=None)
            with mock.patch.dict(os.environ, IDENTITY_ENV):
                exit_code = workflow.command_version_bump(args)
            self.assertEqual(exit_code, 0)
            self.assertEqual((project / "VERSION").read_text(encoding="utf-8").strip(), "0.1")
            log = subprocess.run(
                [shutil.which("git"), "log", "-1", "--pretty=%s"],
                cwd=project,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(log, "chore(release): v0.1")


if __name__ == "__main__":
    unittest.main()
