from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from .models import InventoryItem, ItemDetails, SearchResult
from .stats import format_stats, select_highlights


RARITIES = {"Yellow", "Green", "Blue", "Epic"}
MODES = {"all", "softcore", "hardcore"}
SORTS = {
    "name": "namelowercase COLLATE NOCASE ASC, Id ASC",
    "level_desc": "LevelRequirement DESC, namelowercase COLLATE NOCASE ASC, Id ASC",
    "level_asc": "LevelRequirement ASC, namelowercase COLLATE NOCASE ASC, Id ASC",
    "recent": "created_at DESC, Id DESC",
}
REQUIRED_COLUMNS = {
    "Id",
    "Name",
    "namelowercase",
    "Rarity",
    "LevelRequirement",
    "IsHardcore",
    "Mod",
    "StackCount",
}

SLOT_NAMES = {
    "ArmorProtective_Head": "Head Armor",
    "ArmorProtective_Chest": "Chest Armor",
    "ArmorProtective_Legs": "Leg Armor",
    "ArmorProtective_Feet": "Boots",
    "ArmorProtective_Hands": "Gloves",
    "ArmorProtective_Shoulders": "Shoulders",
    "ArmorProtective_Waist": "Belt",
    "ArmorJewelry_Amulet": "Amulet",
    "ArmorJewelry_Ring": "Ring",
    "ArmorJewelry_Medal": "Medal",
    "ItemArtifact": "Relic",
    "WeaponArmor_Offhand": "Caster Off-hand",
    "WeaponArmor_Shield": "Shield",
    "WeaponMelee_Sword": "One-handed Sword",
    "WeaponMelee_Sword2h": "Two-handed Sword",
    "WeaponMelee_Mace": "One-handed Mace",
    "WeaponMelee_Mace2h": "Two-handed Mace",
    "WeaponMelee_Axe": "One-handed Axe",
    "WeaponMelee_Axe2h": "Two-handed Axe",
    "WeaponMelee_Dagger": "Dagger",
    "WeaponMelee_Scepter": "Scepter",
    "WeaponHunting_Ranged1h": "One-handed Ranged",
    "WeaponHunting_Ranged2h": "Two-handed Ranged",
}


class InventoryError(RuntimeError):
    pass


class InventoryRepository:
    def __init__(self, database: Path):
        self.database = Path(database)

    def _connect(self) -> sqlite3.Connection:
        if not self.database.is_file():
            raise InventoryError("Item Assistant database was not found")
        uri = f"file:{quote(str(self.database))}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=2.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA busy_timeout = 2000")
        return connection

    def validate(self) -> bool:
        try:
            with closing(self._connect()) as connection:
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(PlayerItem)")
                }
                return REQUIRED_COLUMNS.issubset(columns)
        except (InventoryError, sqlite3.Error):
            return False

    def item_count(self) -> int:
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    "SELECT count(*) FROM PlayerItem WHERE coalesce(StackCount, 0) > 0"
                ).fetchone()
                return int(row[0]) if row is not None else 0
        except (InventoryError, sqlite3.Error):
            return 0

    def get_item(self, player_item_id: int) -> InventoryItem | None:
        if not isinstance(player_item_id, int) or isinstance(player_item_id, bool):
            return None
        if player_item_id <= 0 or player_item_id > 9_223_372_036_854_775_807:
            return None
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    """
                    SELECT Id, Name, Rarity, LevelRequirement, IsHardcore, Mod, StackCount
                    FROM PlayerItem
                    WHERE Id = ? AND coalesce(StackCount, 0) > 0
                    """,
                    (player_item_id,),
                ).fetchone()
                return self._to_item(row) if row is not None else None
        except (InventoryError, sqlite3.Error):
            return None

    def get_details(self, player_item_id: int) -> ItemDetails | None:
        if not self._valid_item_id(player_item_id):
            return None
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    """
                    SELECT Id, baserecord, Name, Rarity, LevelRequirement,
                           IsHardcore, Mod, StackCount, created_at
                    FROM PlayerItem
                    WHERE Id = ? AND coalesce(StackCount, 0) > 0
                    """,
                    (player_item_id,),
                ).fetchone()
                if row is None:
                    return None
                stats_by_id = self._load_stats(connection, [player_item_id])
                slots_by_record = self._load_slots(connection, [str(row["baserecord"] or "")])
                raw_stats = stats_by_id.get(player_item_id, ())
                item = self._to_item(
                    row,
                    slot=slots_by_record.get(str(row["baserecord"] or "").lower(), ""),
                    highlights=select_highlights(raw_stats),
                )
                return ItemDetails(item=item, stats=format_stats(raw_stats))
        except (InventoryError, sqlite3.Error):
            return None

    def search(self, filters: dict | None = None) -> SearchResult:
        data = filters if isinstance(filters, dict) else {}
        query = str(data.get("query", "")).strip()[:100]
        rarity = str(data.get("rarity", "all"))
        mode = str(data.get("mode", "all"))
        sort = str(data.get("sort", "name"))
        minimum_level = self._bounded_int(data.get("minimumLevel"), 0, 100, 0)
        maximum_level = self._bounded_int(data.get("maximumLevel"), 0, 100, 100)
        offset = self._bounded_int(data.get("offset"), 0, 1_000_000, 0)
        limit = self._bounded_int(data.get("limit"), 1, 50, 30)

        if rarity != "all" and rarity not in RARITIES:
            rarity = "all"
        if mode not in MODES:
            mode = "all"
        if sort not in SORTS:
            sort = "name"
        if minimum_level > maximum_level:
            minimum_level, maximum_level = maximum_level, minimum_level

        clauses = [
            "coalesce(StackCount, 0) > 0",
            "coalesce(Name, '') <> ''",
            "coalesce(LevelRequirement, 0) BETWEEN ? AND ?",
        ]
        parameters: list[object] = [minimum_level, maximum_level]

        if query:
            escaped = (
                query.lower()
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            clauses.append("coalesce(namelowercase, lower(Name)) LIKE ? ESCAPE '\\'")
            parameters.append(f"%{escaped}%")
        if rarity != "all":
            clauses.append("Rarity = ?")
            parameters.append(rarity)
        if mode == "softcore":
            clauses.append("coalesce(IsHardcore, 0) = 0")
        elif mode == "hardcore":
            clauses.append("coalesce(IsHardcore, 0) <> 0")

        where = " AND ".join(clauses)
        try:
            with closing(self._connect()) as connection:
                total_row = connection.execute(
                    f"SELECT count(*) FROM PlayerItem WHERE {where}", parameters
                ).fetchone()
                total = int(total_row[0]) if total_row is not None else 0
                rows = connection.execute(
                    f"""
                    SELECT Id, baserecord, Name, Rarity, LevelRequirement,
                           IsHardcore, Mod, StackCount, created_at
                    FROM PlayerItem
                    WHERE {where}
                    ORDER BY {SORTS[sort]}
                    LIMIT ? OFFSET ?
                    """,
                    [*parameters, limit, offset],
                ).fetchall()
                item_ids = [int(row["Id"]) for row in rows]
                base_records = [str(row["baserecord"] or "") for row in rows]
                stats_by_id = self._load_stats(connection, item_ids)
                slots_by_record = self._load_slots(connection, base_records)
        except (InventoryError, sqlite3.Error) as exc:
            raise InventoryError("Could not search the Item Assistant database") from exc

        return SearchResult(
            items=[
                self._to_item(
                    row,
                    slot=slots_by_record.get(str(row["baserecord"] or "").lower(), ""),
                    highlights=select_highlights(stats_by_id.get(int(row["Id"]), ())),
                )
                for row in rows
            ],
            total=total,
            offset=offset,
            limit=limit,
        )

    @staticmethod
    def _bounded_int(value: object, minimum: int, maximum: int, default: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError, OverflowError):
            return default
        return min(maximum, max(minimum, parsed))

    @staticmethod
    def _valid_item_id(player_item_id: object) -> bool:
        return (
            isinstance(player_item_id, int)
            and not isinstance(player_item_id, bool)
            and 0 < player_item_id <= 9_223_372_036_854_775_807
        )

    @staticmethod
    def _load_stats(
        connection: sqlite3.Connection, item_ids: list[int]
    ) -> dict[int, tuple[tuple[str, float], ...]]:
        if not item_ids:
            return {}
        placeholders = ",".join("?" for _ in item_ids)
        rows = connection.execute(
            f"""
            SELECT playeritemid, stat, value
            FROM ComputedItemStat
            WHERE playeritemid IN ({placeholders}) AND stat <> '__computed__'
            """,
            item_ids,
        ).fetchall()
        grouped: dict[int, list[tuple[str, float]]] = {}
        for row in rows:
            grouped.setdefault(int(row["playeritemid"]), []).append(
                (str(row["stat"]), float(row["value"] or 0))
            )
        return {key: tuple(value) for key, value in grouped.items()}

    @staticmethod
    def _load_slots(
        connection: sqlite3.Connection, base_records: list[str]
    ) -> dict[str, str]:
        normalized = sorted({record.lower() for record in base_records if record})
        if not normalized:
            return {}
        placeholders = ",".join("?" for _ in normalized)
        rows = connection.execute(
            f"""
            SELECT lower(d.baserecord) AS baserecord, s.TextValue AS item_class
            FROM DatabaseItem_v2 d
            JOIN DatabaseItemStat_v2 s ON s.id_databaseitem = d.id_databaseitem
            WHERE s.Stat = 'Class' AND lower(d.baserecord) IN ({placeholders})
            """,
            normalized,
        ).fetchall()
        return {
            str(row["baserecord"]): SLOT_NAMES.get(
                str(row["item_class"] or ""), str(row["item_class"] or "")
            )
            for row in rows
        }

    @staticmethod
    def _stored_at(value: object) -> str:
        if value in (None, ""):
            return ""
        try:
            numeric = float(value)
            if numeric > 10_000_000_000:
                numeric /= 1000
            return datetime.fromtimestamp(numeric, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        except (TypeError, ValueError, OverflowError, OSError):
            return str(value)

    @staticmethod
    def _to_item(
        row: sqlite3.Row,
        slot: str = "",
        highlights=(),
    ) -> InventoryItem:
        level = int(round(float(row["LevelRequirement"] or 0)))
        keys = set(row.keys())
        return InventoryItem(
            player_item_id=int(row["Id"]),
            name=str(row["Name"] or "Unknown item"),
            rarity=str(row["Rarity"] or "Unknown"),
            level=level,
            hardcore=bool(row["IsHardcore"]),
            mod=str(row["Mod"] or ""),
            stack_count=max(1, int(row["StackCount"] or 1)),
            slot=slot,
            stored_at=InventoryRepository._stored_at(row["created_at"]) if "created_at" in keys else "",
            highlights=tuple(highlights),
        )
