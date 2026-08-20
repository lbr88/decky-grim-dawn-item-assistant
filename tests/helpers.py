from __future__ import annotations

import sqlite3
from contextlib import closing
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
    with closing(sqlite3.connect(database)) as connection:
        connection.execute(
            """
            CREATE TABLE PlayerItem (
                Id INTEGER PRIMARY KEY,
                baserecord TEXT,
                Name TEXT,
                namelowercase TEXT,
                Rarity TEXT,
                LevelRequirement REAL,
                IsHardcore INTEGER,
                Mod TEXT,
                StackCount INTEGER,
                created_at INTEGER
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO PlayerItem (
                Id, baserecord, Name, namelowercase, Rarity, LevelRequirement,
                IsHardcore, Mod, StackCount, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "records/aetherfire.dbr", "Aetherfire", "aetherfire", "Blue", 84, 0, "", 1, 1767225600000),
                (2, "records/verdant-claw.dbr", "Verdant Claw", "verdant claw", "Green", 50, 1, "", 2, 1767312000000),
                (3, "records/proof.dbr", "100% Proof", "100% proof", "Yellow", 10, 0, "", 1, 1767398400000),
                (4, "records/gone.dbr", "Transferred Away", "transferred away", "Epic", 75, 0, "", 0, 1767484800000),
                (5, "records/blade.dbr", "Aether_Blade", "aether_blade", "Epic", 94, 0, "mod_x", 1, 1767571200000),
            ],
        )
        connection.execute(
            "CREATE TABLE ComputedItemStat (Id INTEGER PRIMARY KEY, playeritemid INTEGER, stat TEXT, value REAL)"
        )
        connection.executemany(
            "INSERT INTO ComputedItemStat (playeritemid, stat, value) VALUES (?, ?, ?)",
            [
                (1, "__computed__", 1),
                (1, "defensiveProtection", 812),
                (1, "characterOffensiveAbility", 74),
                (1, "defensiveAether", 28),
                (1, "offensiveAetherModifier", 102),
                (2, "characterLife", 420),
            ],
        )
        connection.execute(
            "CREATE TABLE DatabaseItem_v2 (id_databaseitem INTEGER PRIMARY KEY, baserecord TEXT, name TEXT)"
        )
        connection.execute(
            "CREATE TABLE DatabaseItemStat_v2 (id_databaseitemstat INTEGER PRIMARY KEY, id_databaseitem INTEGER, Stat TEXT, TextValue TEXT, val1 REAL)"
        )
        connection.executemany(
            "INSERT INTO DatabaseItem_v2 (id_databaseitem, baserecord, name) VALUES (?, ?, ?)",
            [(1, "records/aetherfire.dbr", "Aetherfire"), (2, "records/verdant-claw.dbr", "Verdant Claw")],
        )
        connection.executemany(
            "INSERT INTO DatabaseItemStat_v2 (id_databaseitem, Stat, TextValue) VALUES (?, ?, ?)",
            [(1, "Class", "ArmorProtective_Chest"), (2, "Class", "WeaponMelee_Sword")],
        )
        connection.commit()
