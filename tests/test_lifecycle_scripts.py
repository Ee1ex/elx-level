from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_NAMES = (
    "install.ps1",
    "install.sh",
    "update.ps1",
    "update.sh",
    "uninstall.ps1",
    "uninstall.sh",
)


class LifecycleScriptTests(unittest.TestCase):
    def _read(self, name: str) -> str:
        return (ROOT / "scripts" / name).read_text(encoding="utf-8")

    def test_all_lifecycle_scripts_exist_and_support_dry_run(self) -> None:
        for name in SCRIPT_NAMES:
            with self.subTest(script=name):
                path = ROOT / "scripts" / name
                self.assertTrue(path.is_file(), f"缺少生命周期脚本：{name}")
                content = self._read(name).lower()
                self.assertIn("dryrun" if name.endswith(".ps1") else "dry-run", content)

    def test_scripts_include_path_safety_and_chinese_errors(self) -> None:
        for name in SCRIPT_NAMES:
            with self.subTest(script=name):
                content = self._read(name)
                self.assertIn("错误", content)
                self.assertIn("elx-level", content)
                self.assertIn("project-level-workflow", content)
                if name.endswith(".ps1"):
                    self.assertIn("GetFullPath", content)
                    self.assertIn("-LiteralPath", content)
                else:
                    self.assertIn("set -euo pipefail", content)
                    self.assertIn('"$target"', content)

    def test_install_and_update_have_version_and_conflict_backup_policy(self) -> None:
        for name in ("install.ps1", "install.sh", "update.ps1", "update.sh"):
            with self.subTest(script=name):
                content = self._read(name).lower()
                self.assertIn("version", content)
                self.assertIn("backup", content)
                self.assertIn("conflict", content)

    def test_installers_include_only_the_unified_level_document(self) -> None:
        for name in ("install.ps1", "install.sh"):
            content = self._read(name)
            self.assertIn("package-files.json", content)
            self.assertIn("LEVEL.md", (ROOT / "package-files.json").read_text())
            self.assertNotIn("LEVEL1-", content)
            self.assertNotIn("LEVEL2-", content)
            self.assertNotIn("LEVEL3-", content)
            self.assertNotIn("LEVEL4-", content)

    def test_installers_include_bilingual_readme_assets(self) -> None:
        for name in ("install.ps1", "install.sh"):
            with self.subTest(script=name):
                content = self._read(name)
                self.assertIn("package-files.json", content)
                manifest = (ROOT / "package-files.json").read_text()
                self.assertIn("README.en.md", manifest)
                self.assertIn("assets", manifest)

    def test_update_runs_doctor_and_state_migration_before_replacement(self) -> None:
        for name in ("update.ps1", "update.sh"):
            with self.subTest(script=name):
                content = self._read(name).lower()
                self.assertIn("doctor", content)
                self.assertIn("migrate", content)

    def test_installers_validate_and_copy_embedded_core(self) -> None:
        for name in ("install.ps1", "install.sh"):
            with self.subTest(script=name):
                content = self._read(name)
                self.assertIn("validate-package", content)
                self.assertIn("core", content)
                self.assertIn("PVS 内核", content)
                self.assertIn("project-vibe-spec", content)

    def test_install_and_update_enforce_two_part_package_contract(self) -> None:
        for name in ("install.ps1", "install.sh", "update.ps1", "update.sh"):
            with self.subTest(script=name):
                content = self._read(name)
                self.assertIn("两段版本（X.X）", content)
                self.assertTrue("validate-package" in content or "doctor" in content)

    def test_lifecycle_contract_mentions_new_routing_and_memory_files(self) -> None:
        expected = (
            "documentation-contract.md",
            "personal-execution-loop.md",
            "level4-capability-routing.md",
            "github-plugin-routing.md",
            "change-record.md",
            "release-record.md",
            "architecture.md",
            "progress-record.md",
        )
        combined = "\n".join(
            self._read(name) for name in ("install.ps1", "install.sh", "update.ps1", "update.sh")
        )
        for filename in expected:
            self.assertIn(filename, combined)

    def test_uninstall_preserves_project_state_and_project_docs(self) -> None:
        for name in ("uninstall.ps1", "uninstall.sh"):
            with self.subTest(script=name):
                content = self._read(name)
                self.assertIn(".elx-level", content)
                self.assertIn("docs/elx-level", content)
                self.assertIn(".project-workflow", content)
                self.assertIn("旧状态", content)
                self.assertIn("保留", content)

    def test_lifecycle_targets_elx_level_and_preserves_legacy_install(self) -> None:
        for name in SCRIPT_NAMES:
            with self.subTest(script=name):
                content = self._read(name)
                self.assertIn("elx-level", content)
                self.assertIn("project-level-workflow", content)
        for name in ("install.ps1", "install.sh"):
            with self.subTest(script=name):
                content = self._read(name)
                self.assertIn("旧 Skill", content)
                self.assertIn("保留", content)

    def test_uninstallers_leave_independent_pvs_untouched(self) -> None:
        for name in ("uninstall.ps1", "uninstall.sh"):
            with self.subTest(script=name):
                content = self._read(name)
                self.assertIn("独立 project-vibe-spec", content)
                self.assertIn("不处理", content)

    def test_powershell_avoids_cross_shell_and_string_execution(self) -> None:
        forbidden = ("cmd /c", "bash -c", "sh -c", "Invoke-Expression", "iex ", "Start-Process")
        for name in ("install.ps1", "update.ps1", "uninstall.ps1"):
            with self.subTest(script=name):
                content = self._read(name)
                self.assertIn("Set-StrictMode -Version Latest", content)
                self.assertIn("$ErrorActionPreference = 'Stop'", content)
                for item in forbidden:
                    self.assertNotIn(item, content)

    def test_shell_scripts_quote_copy_move_and_remove_targets(self) -> None:
        for name in ("install.sh", "update.sh", "uninstall.sh"):
            with self.subTest(script=name):
                content = self._read(name)
                self.assertNotIn("eval ", content)
                self.assertNotIn("rm -rf $target", content)
                self.assertNotIn("cp -R $", content)
                self.assertNotIn("mv $", content)


if __name__ == "__main__":
    unittest.main()
