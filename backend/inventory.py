from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import quote

from .models import InventoryItem, SearchResult


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
            with self._connect() as connection:
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(PlayerItem)")
                }
                return REQUIRED_COLUMNS.issubset(columns)
        except (InventoryError, sqlite3.Error):
            return False

    def item_count(self) -> int:
        try:
            with self._connect() as connection:
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
            with self._connect() as connection:
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
            with self._connect() as connection:
                total_row = connection.execute(
                    f"SELECT count(*) FROM PlayerItem WHERE {where}", parameters
                ).fetchone()
                total = int(total_row[0]) if total_row is not None else 0
                rows = connection.execute(
                    f"""
                    SELECT Id, Name, Rarity, LevelRequirement, IsHardcore, Mod, StackCount
                    FROM PlayerItem
                    WHERE {where}
                    ORDER BY {SORTS[sort]}
                    LIMIT ? OFFSET ?
                    """,
                    [*parameters, limit, offset],
                ).fetchall()
        except (InventoryError, sqlite3.Error) as exc:
            raise InventoryError("Could not search the Item Assistant database") from exc

        return SearchResult(
            items=[self._to_item(row) for row in rows],
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
    def _to_item(row: sqlite3.Row) -> InventoryItem:
        level = int(round(float(row["LevelRequirement"] or 0)))
        return InventoryItem(
            player_item_id=int(row["Id"]),
            name=str(row["Name"] or "Unknown item"),
            rarity=str(row["Rarity"] or "Unknown"),
            level=level,
            hardcore=bool(row["IsHardcore"]),
            mod=str(row["Mod"] or ""),
            stack_count=max(1, int(row["StackCount"] or 1)),
        )
