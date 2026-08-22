from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.paths import GdiaPaths
from backend.processes import any_process_named, pid_matches, process_name


class PathAndProcessTests(unittest.TestCase):
    def test_path_discovery_uses_expected_app_id_and_allows_test_overrides(self) -> None:
        paths = GdiaPaths.discover(
            environment={
                "GDIA_STEAM_ROOT": "/test/steam",
                "GDIA_PREFIX": "/test/prefix",
                "GDIA_DATA_DIR": "/test/data",
            },
            home=Path("/not-used"),
        )
        self.assertEqual(paths.steam_root, Path("/test/steam"))
        self.assertEqual(paths.prefix, Path("/test/prefix"))
        self.assertEqual(paths.database, Path("/test/data/data/userdata.db"))
        self.assertEqual(paths.bridge_status, Path("/test/data/decky-bridge/status.json"))

    def test_process_matching_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            proc_root = Path(temporary_directory)
            (proc_root / "123").mkdir()
            (proc_root / "123/comm").write_text("IAGrim.exe\n", encoding="utf-8")
            (proc_root / "124").mkdir()
            (proc_root / "124/comm").write_text("IAGrim.exe.bad\n", encoding="utf-8")

            self.assertEqual(process_name(123, proc_root), "IAGrim.exe")
            self.assertTrue(pid_matches(123, "IAGrim.exe", proc_root))
            self.assertFalse(pid_matches(124, "IAGrim.exe", proc_root))
            self.assertTrue(any_process_named("IAGrim.exe", proc_root))
            self.assertFalse(any_process_named("Grim Dawn.exe", proc_root))

    def test_process_matching_survives_wine_main_thread_rename(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            proc_root = Path(temporary_directory)
            (proc_root / "296").mkdir()
            (proc_root / "296/comm").write_text("Main\n", encoding="utf-8")
            (proc_root / "296/cmdline").write_bytes(
                b"C:\\Program Files\\IAGD\\IAGrim.exe\0"
            )

            self.assertTrue(any_process_named("IAGrim.exe", proc_root))

    def test_process_matching_rejects_a_truncated_command_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            proc_root = Path(temporary_directory)
            (proc_root / "297").mkdir()
            (proc_root / "297/comm").write_text("Main\n", encoding="utf-8")
            prefix_length = 4096 - len(b"IAGrim.exe")
            padding = b"C:\\" + (b"x" * (prefix_length - 4)) + b"\\"
            (proc_root / "297/cmdline").write_bytes(
                padding + b"IAGrim.exe.bad\0"
            )

            self.assertFalse(any_process_named("IAGrim.exe", proc_root))


if __name__ == "__main__":
    unittest.main()
