from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from .models import (
    BuildOptions,
    InventoryItem,
    ItemBuildBonus,
    ItemDetails,
    MasteryOption,
    SearchResult,
    SkillOption,
)
from .stats import format_stats, select_highlights


RARITIES = {"Yellow", "Green", "Blue", "Epic"}
MODES = {"all", "softcore", "hardcore"}
SORTS = {
    "name": "p.namelowercase COLLATE NOCASE ASC, p.Id ASC",
    "level_desc": "p.LevelRequirement DESC, p.namelowercase COLLATE NOCASE ASC, p.Id ASC",
    "level_asc": "p.LevelRequirement ASC, p.namelowercase COLLATE NOCASE ASC, p.Id ASC",
    "recent": "p.created_at DESC, p.Id DESC",
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
    "ItemEnchantment": "Augment / Enchantment",
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
    "WeaponMelee_Spear2h": "Two-handed Spear",
    "WeaponHunting_Ranged1h": "One-handed Ranged",
    "WeaponHunting_Ranged2h": "Two-handed Ranged",
}

RESISTANCE_STATS = {
    "fire": (("defensiveElementalResistance", "defensiveFire"), "Fire"),
    "cold": (("defensiveElementalResistance", "defensiveCold"), "Cold"),
    "lightning": (("defensiveElementalResistance", "defensiveLightning"), "Lightning"),
    "pierce": (("defensivePierce",), "Pierce"),
    "poison": (("defensivePoison",), "Poison & Acid"),
    "bleeding": (("defensiveBleeding",), "Bleeding"),
    "vitality": (("defensiveLife",), "Vitality"),
    "aether": (("defensiveAether",), "Aether"),
    "chaos": (("defensiveChaos",), "Chaos"),
}
MASTERY_IDS = {f"class{number:02d}" for number in range(1, 11)}
ITEM_RECORD_COLUMNS = (
    "baserecord",
    "PrefixRecord",
    "SuffixRecord",
    "ModifierRecord",
    "TransmuteRecord",
    "MateriaRecord",
    "RelicCompletionBonusRecord",
    "EnchantmentRecord",
    "AscendantAffixNameRecord",
    "AscendantAffix2hNameRecord",
)


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

    def build_options(self) -> BuildOptions:
        try:
            with closing(self._connect()) as connection:
                tag_rows = connection.execute(
                    "SELECT Tag, Name FROM ItemTag WHERE Tag GLOB 'tagSkillClassName[0-9][0-9]'"
                ).fetchall()
                mastery_names = {
                    f"class{str(row['Tag'])[-2:]}": str(row["Name"] or "")
                    for row in tag_rows
                    if row["Name"]
                }
                mastery_rows = connection.execute(
                    """
                    SELECT DISTINCT TextValue
                    FROM DatabaseItemStat_v2
                    WHERE (
                        Stat GLOB 'augmentMastery[0-9]'
                        OR Stat GLOB 'augmentSkill[0-9]Extras'
                    ) AND TextValue GLOB 'class[0-9][0-9]'
                    """
                ).fetchall()
                mastery_ids = sorted(
                    {
                        str(row["TextValue"])
                        for row in mastery_rows
                        if str(row["TextValue"]) in MASTERY_IDS
                    },
                    key=lambda value: mastery_names.get(value, value),
                )
                skill_rows = connection.execute(
                    """
                    SELECT DISTINCT skill.TextValue AS skill_name,
                                    coalesce(extras.TextValue, '') AS mastery_id
                    FROM DatabaseItemStat_v2 skill
                    LEFT JOIN DatabaseItemStat_v2 extras
                      ON extras.id_databaseitem = skill.id_databaseitem
                     AND extras.Stat = skill.Stat || 'Extras'
                    WHERE skill.Stat GLOB 'augmentSkill[0-9]'
                      AND coalesce(skill.TextValue, '') <> ''
                    ORDER BY skill.TextValue COLLATE NOCASE
                    """
                ).fetchall()
        except (InventoryError, sqlite3.Error) as exc:
            raise InventoryError("Could not read build options") from exc

        masteries = tuple(
            MasteryOption(mastery_id, mastery_names.get(mastery_id, mastery_id))
            for mastery_id in mastery_ids
        )
        skills = tuple(
            SkillOption(
                str(row["skill_name"]),
                str(row["mastery_id"])
                if str(row["mastery_id"]) in MASTERY_IDS
                else "",
            )
            for row in skill_rows
        )
        return BuildOptions(masteries=masteries, skills=skills)

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
                record_select = ", ".join(ITEM_RECORD_COLUMNS)
                row = connection.execute(
                    f"""
                    SELECT Id, {record_select}, Name, Rarity, LevelRequirement,
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
                bonuses_by_id = self._load_build_bonuses(
                    connection, {player_item_id: self._records_from_row(row)}
                )
                raw_stats = stats_by_id.get(player_item_id, ())
                item = self._to_item(
                    row,
                    slot=slots_by_record.get(str(row["baserecord"] or "").lower(), ""),
                    highlights=select_highlights(raw_stats),
                    build_bonuses=bonuses_by_id.get(player_item_id, ()),
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
        slot = str(data.get("slot", "all"))
        resistance = str(data.get("resistance", "all"))
        mastery = str(data.get("mastery", "all"))
        skill = str(data.get("skill", "")).strip()[:100]
        minimum_level = self._bounded_int(data.get("minimumLevel"), 0, 100, 0)
        maximum_level = self._bounded_int(data.get("maximumLevel"), 0, 100, 100)
        minimum_resistance = self._bounded_int(
            data.get("minimumResistance"), 0, 200, 1
        )
        offset = self._bounded_int(data.get("offset"), 0, 1_000_000, 0)
        limit = self._bounded_int(data.get("limit"), 1, 50, 30)

        if rarity != "all" and rarity not in RARITIES:
            rarity = "all"
        if mode not in MODES:
            mode = "all"
        if sort not in SORTS and sort != "resistance_desc":
            sort = "name"
        if slot != "all" and slot not in SLOT_NAMES:
            slot = "all"
        if resistance != "all" and resistance not in RESISTANCE_STATS:
            resistance = "all"
        if mastery != "all" and mastery not in MASTERY_IDS:
            mastery = "all"
        if not skill or len(skill) > 100:
            skill = ""
        if minimum_level > maximum_level:
            minimum_level, maximum_level = maximum_level, minimum_level

        clauses = [
            "coalesce(p.StackCount, 0) > 0",
            "coalesce(p.Name, '') <> ''",
            "coalesce(p.LevelRequirement, 0) BETWEEN ? AND ?",
        ]
        parameters: list[object] = [minimum_level, maximum_level]

        if query:
            escaped = (
                query.lower()
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            clauses.append("coalesce(p.namelowercase, lower(p.Name)) LIKE ? ESCAPE '\\'")
            parameters.append(f"%{escaped}%")
        if rarity != "all":
            clauses.append("p.Rarity = ?")
            parameters.append(rarity)
        if mode == "softcore":
            clauses.append("coalesce(p.IsHardcore, 0) = 0")
        elif mode == "hardcore":
            clauses.append("coalesce(p.IsHardcore, 0) <> 0")

        record_match = self._record_match_sql("d", "p")
        if slot != "all":
            clauses.append(
                f"""EXISTS (
                    SELECT 1 FROM DatabaseItem_v2 d INDEXED BY idx_databaseitemv2_baserecord
                    JOIN DatabaseItemStat_v2 s INDEXED BY idx_databaseitemstatv2_parent
                      ON s.id_databaseitem = d.id_databaseitem
                    WHERE {record_match} AND s.Stat = 'Class' AND s.TextValue = ?
                )"""
            )
            parameters.append(slot)

        resistance_keys: tuple[str, ...] = ()
        if resistance != "all":
            resistance_keys = RESISTANCE_STATS[resistance][0]
            placeholders = ",".join("?" for _ in resistance_keys)
            clauses.append(
                f"""(
                    SELECT coalesce(sum(cis.value), 0)
                    FROM ComputedItemStat cis
                    WHERE cis.playeritemid = p.Id AND cis.stat IN ({placeholders})
                ) >= ?"""
            )
            parameters.extend([*resistance_keys, minimum_resistance])

        if mastery != "all":
            clauses.append(
                f"""EXISTS (
                    SELECT 1 FROM DatabaseItem_v2 d INDEXED BY idx_databaseitemv2_baserecord
                    JOIN DatabaseItemStat_v2 s INDEXED BY idx_databaseitemstatv2_parent
                      ON s.id_databaseitem = d.id_databaseitem
                    WHERE {record_match} AND (
                        (s.Stat GLOB 'augmentMastery[0-9]' AND s.TextValue = ?)
                        OR (s.Stat GLOB 'augmentSkill[0-9]Extras' AND s.TextValue = ?)
                    )
                )"""
            )
            parameters.extend([mastery, mastery])

        if skill:
            clauses.append(
                f"""EXISTS (
                    SELECT 1 FROM DatabaseItem_v2 d INDEXED BY idx_databaseitemv2_baserecord
                    JOIN DatabaseItemStat_v2 s INDEXED BY idx_databaseitemstatv2_parent
                      ON s.id_databaseitem = d.id_databaseitem
                    WHERE {record_match}
                      AND s.Stat GLOB 'augmentSkill[0-9]'
                      AND s.TextValue = ?
                )"""
            )
            parameters.append(skill)

        where = " AND ".join(clauses)
        try:
            with closing(self._connect()) as connection:
                total_row = connection.execute(
                    f"SELECT count(*) FROM PlayerItem p WHERE {where}", parameters
                ).fetchone()
                total = int(total_row[0]) if total_row is not None else 0
                order_by = SORTS.get(sort, SORTS["name"])
                if sort == "resistance_desc" and resistance_keys:
                    resistance_literals = ",".join(
                        f"'{key}'" for key in resistance_keys
                    )
                    order_by = f"""(
                        SELECT coalesce(sum(sort_stats.value), 0)
                        FROM ComputedItemStat sort_stats
                        WHERE sort_stats.playeritemid = p.Id
                          AND sort_stats.stat IN ({resistance_literals})
                    ) DESC, p.LevelRequirement DESC, p.Id ASC"""
                record_select = ", ".join(
                    f"p.{column}" for column in ITEM_RECORD_COLUMNS
                )
                rows = connection.execute(
                    f"""
                    SELECT p.Id, {record_select}, p.Name, p.Rarity,
                           p.LevelRequirement, p.IsHardcore, p.Mod,
                           p.StackCount, p.created_at
                    FROM PlayerItem p
                    WHERE {where}
                    ORDER BY {order_by}
                    LIMIT ? OFFSET ?
                    """,
                    [*parameters, limit, offset],
                ).fetchall()
                item_ids = [int(row["Id"]) for row in rows]
                base_records = [str(row["baserecord"] or "") for row in rows]
                stats_by_id = self._load_stats(connection, item_ids)
                slots_by_record = self._load_slots(connection, base_records)
                item_records = {
                    int(row["Id"]): self._records_from_row(row) for row in rows
                }
                bonuses_by_id = self._load_build_bonuses(connection, item_records)
        except (InventoryError, sqlite3.Error) as exc:
            raise InventoryError("Could not search the Item Assistant database") from exc

        return SearchResult(
            items=[
                self._to_item(
                    row,
                    slot=slots_by_record.get(str(row["baserecord"] or "").lower(), ""),
                    highlights=select_highlights(stats_by_id.get(int(row["Id"]), ())),
                    build_bonuses=bonuses_by_id.get(int(row["Id"]), ()),
                    match_reasons=self._match_reasons(
                        stats_by_id.get(int(row["Id"]), ()),
                        bonuses_by_id.get(int(row["Id"]), ()),
                        resistance,
                        mastery,
                        skill,
                    ),
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
    def _record_match_sql(database_alias: str, player_alias: str) -> str:
        player_records = ", ".join(
            f"coalesce({player_alias}.{column}, '')"
            for column in ITEM_RECORD_COLUMNS
        )
        return f"{database_alias}.baserecord IN ({player_records})"

    @staticmethod
    def _records_from_row(row: sqlite3.Row) -> tuple[str, ...]:
        keys = set(row.keys())
        return tuple(
            str(row[column]).lower()
            for column in ITEM_RECORD_COLUMNS
            if column in keys and row[column]
        )

    @staticmethod
    def _load_build_bonuses(
        connection: sqlite3.Connection,
        item_records: dict[int, tuple[str, ...]],
    ) -> dict[int, tuple[ItemBuildBonus, ...]]:
        all_records = sorted(
            {record for records in item_records.values() for record in records}
        )
        if not all_records:
            return {}
        placeholders = ",".join("?" for _ in all_records)
        stat_rows = connection.execute(
            f"""
            SELECT d.baserecord, s.Stat, s.TextValue, s.val1
            FROM DatabaseItem_v2 d
            JOIN DatabaseItemStat_v2 s ON s.id_databaseitem = d.id_databaseitem
            WHERE d.baserecord IN ({placeholders}) AND (
                s.Stat GLOB 'augmentMastery[0-9]'
                OR s.Stat GLOB 'augmentMasteryLevel[0-9]'
                OR s.Stat GLOB 'augmentSkill[0-9]'
                OR s.Stat GLOB 'augmentSkill[0-9]Extras'
                OR s.Stat GLOB 'augmentSkillLevel[0-9]'
            )
            """,
            all_records,
        ).fetchall()
        granted_rows = connection.execute(
            f"""
            SELECT d.baserecord, skill.Name
            FROM DatabaseItem_v2 d
            JOIN itemskill_v2 skill ON skill.id_databaseitem = d.id_databaseitem
            WHERE d.baserecord IN ({placeholders})
              AND coalesce(skill.Name, '') <> ''
            """,
            all_records,
        ).fetchall()
        tag_rows = connection.execute(
            "SELECT Tag, Name FROM ItemTag WHERE Tag GLOB 'tagSkillClassName[0-9][0-9]'"
        ).fetchall()
        mastery_names = {
            f"class{str(row['Tag'])[-2:]}": str(row["Name"] or "")
            for row in tag_rows
            if row["Name"]
        }

        stats_by_record: dict[str, dict[str, tuple[str, float]]] = {}
        for row in stat_rows:
            stats_by_record.setdefault(str(row["baserecord"]), {})[
                str(row["Stat"])
            ] = (str(row["TextValue"] or ""), float(row["val1"] or 0))
        granted_by_record: dict[str, set[str]] = {}
        for row in granted_rows:
            granted_by_record.setdefault(str(row["baserecord"]), set()).add(
                str(row["Name"])
            )

        result: dict[int, tuple[ItemBuildBonus, ...]] = {}
        for item_id, records in item_records.items():
            totals: dict[tuple[str, str, str], int] = {}
            for record in records:
                record_stats = stats_by_record.get(record, {})
                for index in range(1, 10):
                    mastery = record_stats.get(f"augmentMastery{index}", ("", 0))[0]
                    if mastery in MASTERY_IDS:
                        level = int(
                            round(
                                record_stats.get(
                                    f"augmentMasteryLevel{index}", ("", 0)
                                )[1]
                            )
                        )
                        if level > 0:
                            name = mastery_names.get(mastery, mastery)
                            key = ("mastery", name, mastery)
                            totals[key] = totals.get(key, 0) + level

                    skill_name = record_stats.get(f"augmentSkill{index}", ("", 0))[0]
                    if skill_name:
                        mastery_id = record_stats.get(
                            f"augmentSkill{index}Extras", ("", 0)
                        )[0]
                        if mastery_id not in MASTERY_IDS:
                            mastery_id = ""
                        level = int(
                            round(
                                record_stats.get(
                                    f"augmentSkillLevel{index}", ("", 0)
                                )[1]
                            )
                        )
                        if level > 0:
                            key = ("skill", skill_name, mastery_id)
                            totals[key] = totals.get(key, 0) + level

                for granted_name in granted_by_record.get(record, set()):
                    totals[("granted", granted_name, "")] = 0

            bonuses: list[ItemBuildBonus] = []
            for (kind, name, mastery_id), value in totals.items():
                if kind == "mastery":
                    display = f"+{value} to all skills in {name}"
                elif kind == "skill":
                    display = f"+{value} to {name}"
                else:
                    display = f"Grants {name}"
                bonuses.append(
                    ItemBuildBonus(kind, name, mastery_id, value, display)
                )
            bonuses.sort(
                key=lambda bonus: (
                    {"mastery": 0, "skill": 1, "granted": 2}.get(
                        bonus.kind, 9
                    ),
                    bonus.name.lower(),
                )
            )
            result[item_id] = tuple(bonuses)
        return result

    @staticmethod
    def _match_reasons(
        raw_stats: tuple[tuple[str, float], ...],
        bonuses: tuple[ItemBuildBonus, ...],
        resistance: str,
        mastery: str,
        skill: str,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if resistance in RESISTANCE_STATS:
            keys, label = RESISTANCE_STATS[resistance]
            contribution = sum(
                value for key, value in raw_stats if key in keys
            )
            if contribution > 0:
                formatted = (
                    str(int(round(contribution)))
                    if float(contribution).is_integer()
                    else f"{contribution:.1f}"
                )
                reasons.append(f"+{formatted}% {label} Resistance")
        for bonus in bonuses:
            if skill and bonus.kind == "skill" and bonus.name == skill:
                reasons.append(bonus.display_value)
            elif (
                mastery in MASTERY_IDS
                and bonus.mastery_id == mastery
                and bonus.display_value not in reasons
            ):
                reasons.append(bonus.display_value)
        return tuple(reasons)

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
            SELECT d.baserecord, s.TextValue AS item_class
            FROM DatabaseItem_v2 d
            JOIN DatabaseItemStat_v2 s ON s.id_databaseitem = d.id_databaseitem
            WHERE s.Stat = 'Class' AND d.baserecord IN ({placeholders})
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
        build_bonuses=(),
        match_reasons=(),
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
            build_bonuses=tuple(build_bonuses),
            match_reasons=tuple(match_reasons),
        )
