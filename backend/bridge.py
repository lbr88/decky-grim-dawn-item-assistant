from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Callable

from .models import OperationResult
from .paths import GdiaPaths
from .processes import pid_matches


BRIDGE_VERSION = 1
MAX_STATUS_BYTES = 4096
MAX_RESPONSE_BYTES = 8192


class BridgeClient:
    def __init__(
        self,
        paths: GdiaPaths,
        process_checker: Callable[[int, str], bool] | None = None,
    ):
        self.paths = paths
        self._process_checker = process_checker or pid_matches

    def status(self) -> tuple[bool, int | None]:
        try:
            raw = self.paths.bridge_status.read_bytes()
            if len(raw) > MAX_STATUS_BYTES:
                return False, None
            status = json.loads(raw)
            version = int(status.get("version", 0))
            pid = int(status.get("pid", 0))
            ready = status.get("ready") is True
            if (
                version != BRIDGE_VERSION
                or not ready
                or not self._process_checker(pid, "IAGrim.exe")
            ):
                return False, version or None
            return True, version
        except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
            return False, None

    def transfer(self, player_item_id: int, timeout: float = 8.0) -> OperationResult:
        if (
            not isinstance(player_item_id, int)
            or isinstance(player_item_id, bool)
            or player_item_id <= 0
            or player_item_id > 9_223_372_036_854_775_807
        ):
            return OperationResult(False, "Invalid Item Assistant item ID")

        ready, _ = self.status()
        if not ready:
            return OperationResult(
                False,
                "Item Assistant is not running with the Decky bridge",
            )

        self._ensure_directories()
        request_id = str(uuid.uuid4())
        request_path = self.paths.bridge_requests / f"{request_id}.json"
        response_path = self.paths.bridge_responses / f"{request_id}.json"
        temporary_path = self.paths.bridge_requests / f".{request_id}.tmp"
        payload = {
            "version": BRIDGE_VERSION,
            "requestId": request_id,
            "action": "transfer",
            "playerItemId": player_item_id,
            "createdAt": int(time.time()),
        }
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        descriptor = os.open(
            temporary_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, request_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

        deadline = time.monotonic() + max(1.0, min(timeout, 30.0))
        while time.monotonic() < deadline:
            if response_path.is_file():
                result = self._read_response(response_path, request_id)
                response_path.unlink(missing_ok=True)
                return result
            time.sleep(0.1)

        request_path.unlink(missing_ok=True)
        return OperationResult(
            False,
            "Transfer status is unknown; refresh before trying the item again",
            uncertain=True,
        )

    def _ensure_directories(self) -> None:
        for directory in (
            self.paths.bridge_root,
            self.paths.bridge_requests,
            self.paths.bridge_responses,
        ):
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                directory.chmod(0o700)
            except OSError:
                pass

    @staticmethod
    def _read_response(path: Path, request_id: str) -> OperationResult:
        try:
            raw = path.read_bytes()
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError("response too large")
            response = json.loads(raw)
            if int(response.get("version", 0)) != BRIDGE_VERSION:
                raise ValueError("response version mismatch")
            if response.get("requestId") != request_id:
                raise ValueError("response ID mismatch")
            ok = response.get("ok") is True
            message = str(
                response.get(
                    "message", "Transfer completed" if ok else "Transfer failed"
                )
            )[:240]
            return OperationResult(ok, message)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return OperationResult(False, "Item Assistant returned an invalid bridge response")
