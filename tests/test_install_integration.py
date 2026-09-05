import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InstallIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell"), "PowerShell integration test")
    def test_project_install_is_single_skill_and_preserves_independent_pvs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            skills = project / ".codex" / "skills"
            independent = skills / "project-vibe-spec"
            independent.mkdir(parents=True)
            marker = independent / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            result = subprocess.run(
                [
                    "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "scripts" / "install.ps1"),
                    "-Platform", "codex", "-Scope", "project", "-ProjectPath", str(project),
                ],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
                env={
                    **os.environ,
                    "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
                },
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            installed = skills / "elx-level"
            skill_files = sorted(path.relative_to(installed).as_posix() for path in installed.rglob("SKILL.md"))
            self.assertEqual(skill_files, ["SKILL.md"])
            self.assertTrue((installed / "core" / "project-vibe-spec" / "PVS.md").is_file())
            for relative in (
                "README.en.md",
                "assets/readme/hero.svg",
                "assets/readme/workflow.svg",
                "references/documentation-contract.md",
                "references/personal-execution-loop.md",
                "references/level4-capability-routing.md",
                "references/github-plugin-routing.md",
                "templates/common/change-record.md",
                "templates/common/release-record.md",
                "templates/level1/architecture.md",
                "templates/level1/progress-record.md",
                "templates/level1/project-brief.md",
            ):
                self.assertTrue((installed / relative).is_file(), relative)
            self.assertEqual((installed / "VERSION").read_text(encoding="utf-8").strip(), "2.2")
            for action in ("doctor", "validate-package"):
                check = subprocess.run([sys.executable, str(installed / "scripts/workflow.py"), action,
                                        "--package-root", str(installed)], capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            self.assertFalse((skills / "project-level-workflow").exists())
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
            self.assertIn("独立 project-vibe-spec", result.stdout)

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell"), "PowerShell integration test")
    def test_failed_staged_replacement_restores_previous_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            installed = project / ".codex" / "skills" / "elx-level"
            installed.mkdir(parents=True)
            marker = installed / "keep.txt"
            marker.write_text("previous-install", encoding="utf-8")
            (installed / "VERSION").write_text("0.4.0\n", encoding="utf-8")
            installer = ROOT / "scripts" / "install.ps1"
            command = rf"""
$script:MoveCount = 0
function Move-Item {{
    param([string]$LiteralPath, [string]$Destination)
    $script:MoveCount += 1
    if ($script:MoveCount -eq 2) {{ throw 'injected staged replacement failure' }}
    Microsoft.PowerShell.Management\Move-Item -LiteralPath $LiteralPath -Destination $Destination
}}
try {{
    . '{installer}' -Platform codex -Scope project -ProjectPath '{project}'
}} catch {{
    Write-Output $_.Exception.Message
    exit 23
}}
"""
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
                env={
                    **os.environ,
                    "PATH": str(Path(sys.executable).parent)
                    + os.pathsep
                    + os.environ.get("PATH", ""),
                },
            )
            self.assertEqual(result.returncode, 23, result.stdout + result.stderr)
            self.assertIn("injected staged replacement failure", result.stdout)
            self.assertEqual(marker.read_text(encoding="utf-8"), "previous-install")
            self.assertFalse(list(installed.parent.glob("elx-level.installing-*")))

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell"), "PowerShell integration test")
    def test_install_preserves_legacy_skill_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            skills = project / ".codex" / "skills"
            legacy = skills / "project-level-workflow"
            legacy.mkdir(parents=True)
            marker = legacy / "keep.txt"
            marker.write_text("legacy", encoding="utf-8")
            result = subprocess.run(
                [
                    "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "scripts" / "install.ps1"),
                    "-Platform", "codex", "-Scope", "project", "-ProjectPath", str(project),
                ],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
                env={
                    **os.environ,
                    "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
                },
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(marker.read_text(encoding="utf-8"), "legacy")
            self.assertTrue((skills / "elx-level" / "SKILL.md").is_file())
            self.assertIn("旧 Skill", result.stdout)


if __name__ == "__main__":
    unittest.main()
