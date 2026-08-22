from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from backend.bridge import BRIDGE_VERSION, BridgeClient

from .helpers import make_paths


class BridgeClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.paths = make_paths(self.root)
        self.paths.bridge_root.mkdir(parents=True)
        self.paths.bridge_status.write_text(
            json.dumps(
                {
                    "version": BRIDGE_VERSION,
                    "ready": True,
                    "pid": os.getpid(),
                }
            ),
            encoding="utf-8",
        )
        self.client = BridgeClient(
            self.paths,
            process_checker=lambda name: name == "IAGrim.exe",
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_status_requires_matching_version_ready_flag_and_process(self) -> None:
        self.assertEqual(self.client.status(), (True, BRIDGE_VERSION))
        stopped_client = BridgeClient(
            self.paths,
            process_checker=lambda _name: False,
        )
        self.assertEqual(stopped_client.status(), (False, BRIDGE_VERSION))
        self.paths.bridge_status.write_text(
            json.dumps({"version": 99, "ready": True, "pid": os.getpid()}),
            encoding="utf-8",
        )
        self.assertEqual(self.client.status(), (False, 99))

    def test_status_does_not_treat_a_wine_pid_as_a_linux_proc_pid(self) -> None:
        self.paths.bridge_status.write_text(
            json.dumps({"version": BRIDGE_VERSION, "ready": True, "pid": 292}),
            encoding="utf-8",
        )
        client = BridgeClient(
            self.paths,
            process_checker=lambda *args: args == ("IAGrim.exe",),
        )

        self.assertEqual(client.status(), (True, BRIDGE_VERSION))

    def test_transfer_uses_private_atomic_request_and_valid_response(self) -> None:
        captured: dict = {}

        def respond() -> None:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                requests = list(self.paths.bridge_requests.glob("*.json"))
                if requests:
                    request_path = requests[0]
                    captured.update(json.loads(request_path.read_text(encoding="utf-8")))
                    response = {
                        "version": BRIDGE_VERSION,
                        "requestId": captured["requestId"],
                        "ok": True,
                        "message": "Transferred one item",
                    }
                    response_path = (
                        self.paths.bridge_responses
                        / f"{captured['requestId']}.json"
                    )
                    response_path.write_text(json.dumps(response), encoding="utf-8")
                    return
                time.sleep(0.02)

        responder = threading.Thread(target=respond)
        responder.start()
        result = self.client.transfer(2, timeout=3)
        responder.join(timeout=3)

        self.assertTrue(result.ok)
        self.assertEqual(captured["action"], "transfer")
        self.assertEqual(captured["playerItemId"], 2)
        self.assertEqual(captured["version"], BRIDGE_VERSION)
        mode = self.paths.bridge_requests.stat().st_mode & 0o777
        self.assertEqual(mode, 0o700)

    def test_transfer_rejects_invalid_ids_before_writing(self) -> None:
        for value in (True, 0, -1, 9_223_372_036_854_775_808):
            with self.subTest(value=value):
                result = self.client.transfer(value)
                self.assertFalse(result.ok)
        self.assertFalse(self.paths.bridge_requests.exists())

    def test_transfer_timeout_is_marked_uncertain(self) -> None:
        result = self.client.transfer(1, timeout=0.05)
        self.assertFalse(result.ok)
        self.assertTrue(result.uncertain)
        self.assertEqual(list(self.paths.bridge_requests.glob("*.json")), [])

    def test_invalid_response_version_is_rejected(self) -> None:
        def respond() -> None:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                requests = list(self.paths.bridge_requests.glob("*.json"))
                if requests:
                    request = json.loads(requests[0].read_text(encoding="utf-8"))
                    response_path = (
                        self.paths.bridge_responses / f"{request['requestId']}.json"
                    )
                    response_path.write_text(
                        json.dumps(
                            {
                                "version": 999,
                                "requestId": request["requestId"],
                                "ok": True,
                            }
                        ),
                        encoding="utf-8",
                    )
                    return
                time.sleep(0.02)

        responder = threading.Thread(target=respond)
        responder.start()
        result = self.client.transfer(1, timeout=3)
        responder.join(timeout=3)
        self.assertFalse(result.ok)


if __name__ == "__main__":
    unittest.main()
