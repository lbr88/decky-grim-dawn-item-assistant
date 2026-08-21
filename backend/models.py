from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class OperationResult:
    ok: bool
    message: str
    uncertain: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PluginStatus:
    installed: bool
    database_ready: bool
    item_count: int
    item_assistant_running: bool
    grim_dawn_running: bool
    bridge_ready: bool
    bridge_version: int | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "installed": self.installed,
            "databaseReady": self.database_ready,
            "itemCount": self.item_count,
            "itemAssistantRunning": self.item_assistant_running,
            "grimDawnRunning": self.grim_dawn_running,
            "bridgeReady": self.bridge_ready,
            "bridgeVersion": self.bridge_version,
            "message": self.message,
        }


@dataclass(frozen=True)
class ItemStat:
    key: str
    label: str
    value: float
    display_value: str
    category: str
    priority: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "displayValue": self.display_value,
            "category": self.category,
        }


@dataclass(frozen=True)
class ItemBuildBonus:
    kind: str
    name: str
    mastery_id: str
    value: int
    display_value: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "masteryId": self.mastery_id,
            "value": self.value,
            "displayValue": self.display_value,
        }


@dataclass(frozen=True)
class InventoryItem:
    player_item_id: int
    name: str
    rarity: str
    level: int
    hardcore: bool
    mod: str
    stack_count: int
    slot: str = ""
    stored_at: str = ""
    highlights: tuple[ItemStat, ...] = field(default_factory=tuple)
    build_bonuses: tuple[ItemBuildBonus, ...] = field(default_factory=tuple)
    match_reasons: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "playerItemId": self.player_item_id,
            "name": self.name,
            "rarity": self.rarity,
            "level": self.level,
            "hardcore": self.hardcore,
            "mod": self.mod,
            "stackCount": self.stack_count,
            "slot": self.slot,
            "storedAt": self.stored_at,
            "highlights": [stat.to_dict() for stat in self.highlights],
            "buildBonuses": [bonus.to_dict() for bonus in self.build_bonuses],
            "matchReasons": list(self.match_reasons),
        }


@dataclass(frozen=True)
class ItemDetails:
    item: InventoryItem
    stats: tuple[ItemStat, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "item": self.item.to_dict(),
            "stats": [stat.to_dict() for stat in self.stats],
        }


@dataclass(frozen=True)
class CharacterSummary:
    character_id: str
    name: str
    level: int
    hardcore: bool
    class_name: str
    modified_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "characterId": self.character_id,
            "name": self.name,
            "level": self.level,
            "hardcore": self.hardcore,
            "className": self.class_name,
            "modifiedAt": self.modified_at,
        }


@dataclass(frozen=True)
class MasteryOption:
    mastery_id: str
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"masteryId": self.mastery_id, "name": self.name}


@dataclass(frozen=True)
class SkillOption:
    name: str
    mastery_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "masteryId": self.mastery_id}


@dataclass(frozen=True)
class BuildOptions:
    masteries: tuple[MasteryOption, ...]
    skills: tuple[SkillOption, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "masteries": [mastery.to_dict() for mastery in self.masteries],
            "skills": [skill.to_dict() for skill in self.skills],
        }


@dataclass(frozen=True)
class SearchResult:
    items: list[InventoryItem]
    total: int
    offset: int
    limit: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "total": self.total,
            "offset": self.offset,
            "limit": self.limit,
            "hasMore": self.offset + len(self.items) < self.total,
        }
