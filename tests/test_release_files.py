from __future__ import annotations

import json
import subprocess
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseFileTests(unittest.TestCase):
    def test_plugin_is_non_root_and_manifest_matches_package(self) -> None:
        plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["flags"], [])
        self.assertEqual(plugin["name"], "GD Item Assistant")
        self.assertEqual(package["version"], "0.1.1")

    def test_shell_scripts_parse(self) -> None:
        scripts = [
            ROOT / "scripts/apply-item-assistant-bridge.sh",
            ROOT / "scripts/install-local.sh",
            ROOT / "scripts/install.sh",
            ROOT / "scripts/package-release.sh",
        ]
        subprocess.run(["bash", "-n", *map(str, scripts)], check=True)

    def test_desktop_launcher_is_pinned_and_not_marked_executable(self) -> None:
        launcher = ROOT / "Install-GDIA-Decky.desktop"
        content = launcher.read_text(encoding="utf-8")
        self.assertIn("/v0.1.1/scripts/install.sh", content)
        self.assertFalse(launcher.stat().st_mode & 0o111)

    def test_installer_stages_outside_deckys_watched_plugin_directory(self) -> None:
        content = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
        self.assertIn('staging_parent="${plugin_parent%/*}/.gdia-installer"', content)
        self.assertNotIn('incoming="${plugin_parent}/.', content)

    def test_release_zip_contains_only_expected_runtime_tree(self) -> None:
        archive = ROOT / "dist-release/decky-grim-dawn-item-assistant.zip"
        if not archive.is_file():
            self.skipTest("Run the frontend build and package script first")
        with zipfile.ZipFile(archive) as package:
            names = set(package.namelist())
        root = "decky-grim-dawn-item-assistant/"
        self.assertIn(root + "plugin.json", names)
        self.assertIn(root + "main.py", names)
        self.assertIn(root + "dist/index.js", names)
        self.assertIn(root + "backend/inventory.py", names)
        self.assertFalse(any("tests/" in name for name in names))
        self.assertFalse(any(name.endswith("DeckyBridgeController.cs") for name in names))


if __name__ == "__main__":
    unittest.main()
