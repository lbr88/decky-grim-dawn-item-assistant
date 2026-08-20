from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class GdiaPaths:
    steam_root: Path
    prefix: Path
    item_assistant_dir: Path
    data_dir: Path
    database: Path
    bridge_root: Path
    bridge_requests: Path
    bridge_responses: Path
    bridge_status: Path

    @classmethod
    def discover(
        cls,
        environment: Mapping[str, str] | None = None,
        home: Path | None = None,
    ) -> "GdiaPaths":
        env = environment if environment is not None else os.environ
        user_home = home if home is not None else Path.home()
        steam_root = Path(
            env.get("GDIA_STEAM_ROOT", str(user_home / ".local/share/Steam"))
        ).resolve()
        prefix = Path(
            env.get(
                "GDIA_PREFIX",
                str(steam_root / "steamapps/compatdata/219990/pfx"),
            )
        ).resolve()
        item_assistant_dir = prefix / "drive_c/Program Files/IAGD"
        data_dir = Path(
            env.get(
                "GDIA_DATA_DIR",
                str(
                    prefix
                    / "drive_c/users/steamuser/AppData/Local/EvilSoft/IAGD"
                ),
            )
        ).resolve()
        bridge_root = data_dir / "decky-bridge"
        return cls(
            steam_root=steam_root,
            prefix=prefix,
            item_assistant_dir=item_assistant_dir,
            data_dir=data_dir,
            database=data_dir / "data/userdata.db",
            bridge_root=bridge_root,
            bridge_requests=bridge_root / "requests",
            bridge_responses=bridge_root / "responses",
            bridge_status=bridge_root / "status.json",
        )
