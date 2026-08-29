import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from scripts import workflow


ROOT = Path(__file__).resolve().parents[1]


class PackageValidationTests(unittest.TestCase):
    def test_current_package_passes_deterministic_validation(self) -> None:
        self.assertEqual(workflow.validate_package(ROOT), [])

    def test_validation_reports_missing_required_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            errors = workflow.validate_package(Path(directory))
        self.assertTrue(errors)
        self.assertIn("缺少", " ".join(errors))

    def test_cli_validate_package_returns_zero(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "workflow.py"),
                "validate-package",
                "--package-root",
                str(ROOT),
            ],
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("包验证通过", result.stdout)

    def test_package_validation_reports_elx_level(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "workflow.py"),
                "validate-package",
                "--package-root",
                str(ROOT),
            ],
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertIn(f"包验证通过：elx-level {version}", result.stdout)

    def test_version_is_consistent_across_public_contracts(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        schema = json.loads(
            (ROOT / "schemas" / "workflow-state.schema.json").read_text(encoding="utf-8")
        )
        evals = json.loads((ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(schema["properties"]["schema_version"]["const"], "2.0")
        self.assertEqual(
            schema["properties"]["execution_policy"]["enum"],
            ["AUTO", "CONFIRM", "MANUAL_ONLY"],
        )
        self.assertEqual(schema["properties"]["workflow_version"]["const"], version)
        self.assertEqual(evals["version"], version)
        self.assertIn(f"## [{version}]", changelog)

    def test_three_part_public_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "package"
            shutil.copytree(ROOT, package)
            (package / "VERSION").write_text("1.0.0\n", encoding="utf-8")
            errors = workflow.validate_package(package)
        self.assertIn("两段版本", " ".join(errors))

    def test_package_contract_exposes_four_active_levels(self) -> None:
        self.assertEqual(workflow.LEVEL_DOCUMENT, "LEVEL.md")
        self.assertEqual(set(workflow.LEVEL_MODES), {1, 2, 3, 4})
        self.assertTrue((ROOT / "references" / "project-vibe-spec-bridge.md").is_file())

    def test_embedded_pvs_contract_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "package"
            shutil.copytree(ROOT, package)
            (package / "core" / "project-vibe-spec" / "PVS.md").unlink()
            errors = workflow.validate_package(package)
        self.assertIn("PVS 内核", " ".join(errors))

    def test_nested_pvs_skill_entry_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "package"
            shutil.copytree(ROOT, package)
            nested = package / "core" / "project-vibe-spec" / "SKILL.md"
            nested.write_text("---\nname: project-vibe-spec\n---\n", encoding="utf-8")
            errors = workflow.validate_package(package)
        self.assertIn("第二个 Skill", " ".join(errors))

    def test_external_pvs_install_instruction_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "package"
            shutil.copytree(ROOT, package)
            readme = package / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8")
                + "\ngit clone https://example/project-vibe-spec.git\n",
                encoding="utf-8",
            )
            errors = workflow.validate_package(package)
        self.assertIn("外部 PVS", " ".join(errors))

    def test_external_routing_contracts_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "package"
            shutil.copytree(ROOT, package)
            (package / "references" / "github-plugin-routing.md").unlink()
            errors = workflow.validate_package(package)
        self.assertIn("github-plugin-routing.md", " ".join(errors))

    def test_release_readiness_record_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "package"
            shutil.copytree(ROOT, package)
            readiness = package / "docs" / "release" / "2.0-readiness.md"
            if readiness.exists():
                readiness.unlink()
            errors = workflow.validate_package(package)
        self.assertIn("2.0-readiness.md", " ".join(errors))


if __name__ == "__main__":
    unittest.main()
