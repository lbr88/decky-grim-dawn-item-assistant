from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class InstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.release = self.root / "release"
        self.plugin_parent = self.root / "plugins"
        self.iagd = self.root / "IAGD"
        self.release.mkdir()
        self.plugin_parent.mkdir()
        self.iagd.mkdir()

        self.original = b"verified original Item Assistant assembly"
        self.patched = b"verified patched Item Assistant assembly"
        (self.iagd / "IAGrim.dll").write_bytes(self.original)
        self._create_assets()

        self.environment = {
            **os.environ,
            "GDIA_TEST_MODE": "1",
            "GDIA_RELEASE_BASE_URL": str(self.release),
            "GDIA_PLUGIN_ROOT": str(self.plugin_parent),
            "GDIA_IAGD_DIR": str(self.iagd),
            "GDIA_SKIP_SERVICE_RESTART": "1",
        }

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _create_assets(self) -> None:
        plugin_stage = self.root / "plugin-stage/decky-grim-dawn-item-assistant"
        (plugin_stage / "dist").mkdir(parents=True)
        (plugin_stage / "backend").mkdir()
        (plugin_stage / "plugin.json").write_text(
            json.dumps({"name": "GD Item Assistant", "flags": []}),
            encoding="utf-8",
        )
        (plugin_stage / "package.json").write_text(
            json.dumps({"version": "0.1.0"}), encoding="utf-8"
        )
        (plugin_stage / "main.py").write_text("class Plugin: pass\n", encoding="utf-8")
        (plugin_stage / "dist/index.js").write_text("export default {};\n", encoding="utf-8")
        (plugin_stage / "backend/__init__.py").write_text("", encoding="utf-8")

        plugin_zip = self.release / "decky-grim-dawn-item-assistant.zip"
        with zipfile.ZipFile(plugin_zip, "w") as archive:
            for path in sorted(plugin_stage.parent.rglob("*")):
                archive.write(path, path.relative_to(plugin_stage.parent))

        bridge_stage = self.root / "bridge-stage"
        bridge_stage.mkdir()
        (bridge_stage / "IAGrim.dll").write_bytes(self.patched)
        (bridge_stage / "bridge-manifest.json").write_text(
            json.dumps(
                {
                    "bridgeVersion": 1,
                    "pluginVersion": "0.1.0",
                    "itemAssistantVersion": "1.5.9700.13021",
                    "sourceCommit": "b6f4e6f0fbb8f9b43d92af2f1380ef2a6f8eb1cb",
                    "originalDllSha256": hashlib.sha256(self.original).hexdigest(),
                    "patchedDllSha256": hashlib.sha256(self.patched).hexdigest(),
                }
            ),
            encoding="utf-8",
        )
        bridge_zip = self.release / "iagd-decky-bridge.zip"
        with zipfile.ZipFile(bridge_zip, "w") as archive:
            archive.write(bridge_stage / "IAGrim.dll", "IAGrim.dll")
            archive.write(
                bridge_stage / "bridge-manifest.json", "bridge-manifest.json"
            )

        (self.release / "SHA256SUMS").write_text(
            f"{sha256(plugin_zip)} decky-grim-dawn-item-assistant.zip\n"
            f"{sha256(bridge_zip)} iagd-decky-bridge.zip\n",
            encoding="utf-8",
        )

    def _run_installer(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(ROOT / "scripts/install.sh")],
            env=self.environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_install_and_repeat_are_safe_and_idempotent(self) -> None:
        first = self._run_installer()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual((self.iagd / "IAGrim.dll").read_bytes(), self.patched)
        self.assertEqual(
            (self.iagd / "IAGrim.dll.pre-decky").read_bytes(), self.original
        )
        installed = self.plugin_parent / "decky-grim-dawn-item-assistant"
        self.assertTrue((installed / "dist/index.js").is_file())

        backup_mtime = (self.iagd / "IAGrim.dll.pre-decky").stat().st_mtime_ns
        second = self._run_installer()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("bridge is already installed; skipping", second.stdout)
        self.assertIn("plugin 0.1.0 is already installed; skipping", second.stdout)
        self.assertIn("Everything is already up to date", second.stdout)
        self.assertEqual(
            (self.iagd / "IAGrim.dll.pre-decky").stat().st_mtime_ns,
            backup_mtime,
        )

    def test_unknown_item_assistant_build_is_refused(self) -> None:
        (self.iagd / "IAGrim.dll").write_bytes(b"unknown build")
        result = self._run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not the verified original", result.stderr)
        self.assertFalse((self.iagd / "IAGrim.dll.pre-decky").exists())
        self.assertFalse(
            (self.plugin_parent / "decky-grim-dawn-item-assistant").exists()
        )


if __name__ == "__main__":
    unittest.main()
