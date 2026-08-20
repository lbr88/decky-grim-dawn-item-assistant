from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.paths import GdiaPaths


def make_paths(root: Path) -> GdiaPaths:
    steam_root = root / "Steam"
    prefix = steam_root / "steamapps/compatdata/219990/pfx"
    item_assistant_dir = prefix / "drive_c/Program Files/IAGD"
    data_dir = (
        prefix / "drive_c/users/steamuser/AppData/Local/EvilSoft/IAGD"
    )
    bridge_root = data_dir / "decky-bridge"
    return GdiaPaths(
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


def create_inventory_database(database: Path) -> None:
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE PlayerItem (
                Id INTEGER PRIMARY KEY,
                Name TEXT,
                namelowercase TEXT,
                Rarity TEXT,
                LevelRequirement REAL,
                IsHardcore INTEGER,
                Mod TEXT,
                StackCount INTEGER,
                created_at TEXT
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO PlayerItem (
                Id, Name, namelowercase, Rarity, LevelRequirement,
                IsHardcore, Mod, StackCount, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "Aetherfire", "aetherfire", "Blue", 84, 0, "", 1, "2026-01-01"),
                (2, "Verdant Claw", "verdant claw", "Green", 50, 1, "", 2, "2026-01-02"),
                (3, "100% Proof", "100% proof", "Yellow", 10, 0, "", 1, "2026-01-03"),
                (4, "Transferred Away", "transferred away", "Epic", 75, 0, "", 0, "2026-01-04"),
                (5, "Aether_Blade", "aether_blade", "Epic", 94, 0, "mod_x", 1, "2026-01-05"),
            ],
        )
