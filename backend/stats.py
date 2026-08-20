from __future__ import annotations

import re
from collections.abc import Iterable

from .models import ItemStat


_EXACT: dict[str, tuple[str, str, str, int | None]] = {
    "defensiveProtection": ("Armor", "{value} Armor", "Defense", 10),
    "defensiveProtectionModifier": ("Armor", "+{value}% Armor", "Defense", 35),
    "characterLife": ("Health", "+{value} Health", "Defense", 20),
    "characterLifeModifier": ("Health", "+{value}% Health", "Defense", 21),
    "characterMana": ("Energy", "+{value} Energy", "Resources", 62),
    "characterManaModifier": ("Energy", "+{value}% Energy", "Resources", 63),
    "characterManaRegen": ("Energy Regeneration", "+{value} Energy Regenerated per Second", "Resources", 64),
    "characterManaRegenModifier": ("Energy Regeneration", "+{value}% Energy Regeneration", "Resources", 65),
    "characterOffensiveAbility": ("Offensive Ability", "+{value} Offensive Ability", "Offense", 11),
    "characterOffensiveAbilityModifier": ("Offensive Ability", "+{value}% Offensive Ability", "Offense", 31),
    "characterDefensiveAbility": ("Defensive Ability", "+{value} Defensive Ability", "Defense", 12),
    "characterDefensiveAbilityModifier": ("Defensive Ability", "+{value}% Defensive Ability", "Defense", 32),
    "characterAttackSpeedModifier": ("Attack Speed", "+{value}% Attack Speed", "Speed", 40),
    "characterSpellCastSpeedModifier": ("Casting Speed", "+{value}% Casting Speed", "Speed", 41),
    "characterRunSpeedModifier": ("Movement Speed", "+{value}% Movement Speed", "Speed", 42),
    "skillCooldownReduction": ("Skill Cooldown", "-{value}% Skill Cooldown", "Utility", 43),
    "offensiveTotalDamageModifier": ("All Damage", "+{value}% All Damage", "Offense", 44),
    "offensiveCritDamageModifier": ("Critical Damage", "+{value}% Critical Damage", "Offense", 45),
    "offensiveLifeLeechMin": ("Attack Damage Converted to Health", "{value}% Attack Damage Converted to Health", "Offense", 46),
    "defensivePhysical": ("Physical Resistance", "+{value}% Physical Resistance", "Defense", 13),
    "defensiveBlock": ("Blocked Damage", "{value} Damage Blocked", "Defense", 50),
    "defensiveBlockChance": ("Block Chance", "{value}% Chance to Block", "Defense", 51),
    "blockAbsorption": ("Block Absorption", "{value}% Block Absorption", "Defense", 52),
    "offensivePierceRatioMin": ("Armor Piercing", "{value}% Armor Piercing", "Offense", 53),
}

_RESISTANCES = {
    "ElementalResistance": "Elemental",
    "Fire": "Fire",
    "Cold": "Cold",
    "Lightning": "Lightning",
    "Poison": "Poison & Acid",
    "Pierce": "Pierce",
    "Bleeding": "Bleeding",
    "Life": "Vitality",
    "Aether": "Aether",
    "Chaos": "Chaos",
    "Stun": "Stun",
    "Freeze": "Freeze",
    "Sleep": "Sleep",
    "Petrify": "Petrify",
    "Trap": "Trap",
    "Knockdown": "Knockdown",
    "TotalSpeedResistance": "Slow",
}

_DAMAGE_TYPES = {
    "Physical": "Physical",
    "Pierce": "Pierce",
    "Fire": "Fire",
    "Cold": "Cold",
    "Lightning": "Lightning",
    "Elemental": "Elemental",
    "Poison": "Acid",
    "Life": "Vitality",
    "Aether": "Aether",
    "Chaos": "Chaos",
    "Bleeding": "Bleeding",
    "SlowPhysical": "Internal Trauma",
    "SlowFire": "Burn",
    "SlowCold": "Frostburn",
    "SlowLightning": "Electrocute",
    "SlowPoison": "Poison",
    "SlowLife": "Vitality Decay",
    "SlowBleeding": "Bleeding",
}

_ATTRIBUTES = {
    "characterStrength": "Physique",
    "characterDexterity": "Cunning",
    "characterIntelligence": "Spirit",
}


def _number(value: float) -> str:
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return f"{int(rounded):,}"
    return f"{rounded:,.2f}".rstrip("0").rstrip(".")


def _humanize(key: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", " ", key).strip().title()


def format_stat(key: str, value: float) -> ItemStat:
    numeric = float(value)
    formatted = _number(numeric)
    if key in _EXACT:
        label, template, category, priority = _EXACT[key]
        return ItemStat(key, label, numeric, template.format(value=formatted), category, priority)

    if key.startswith("defensive"):
        suffix = key.removeprefix("defensive")
        resistance = _RESISTANCES.get(suffix)
        if resistance:
            label = f"{resistance} Resistance"
            return ItemStat(key, label, numeric, f"+{formatted}% {label}", "Resistances", 14)

    if key.startswith("offensive") and key.endswith("Modifier"):
        suffix = key.removeprefix("offensive").removesuffix("Modifier")
        damage = _DAMAGE_TYPES.get(suffix)
        if damage:
            label = f"{damage} Damage"
            return ItemStat(key, label, numeric, f"+{formatted}% {label}", "Damage", 55)

    for attribute_key, attribute_name in _ATTRIBUTES.items():
        if key == attribute_key:
            return ItemStat(key, attribute_name, numeric, f"+{formatted} {attribute_name}", "Attributes", 60)
        if key == f"{attribute_key}Modifier":
            return ItemStat(key, attribute_name, numeric, f"+{formatted}% {attribute_name}", "Attributes", 61)

    label = _humanize(key)
    return ItemStat(key, label, numeric, f"{formatted} {label}", "Other", None)


def format_stats(rows: Iterable[tuple[str, float]]) -> tuple[ItemStat, ...]:
    stats = [format_stat(str(key), float(value)) for key, value in rows if key != "__computed__"]
    category_order = {
        "Defense": 0,
        "Resistances": 1,
        "Offense": 2,
        "Damage": 3,
        "Speed": 4,
        "Attributes": 5,
        "Resources": 6,
        "Utility": 7,
        "Other": 8,
    }
    return tuple(sorted(stats, key=lambda stat: (category_order.get(stat.category, 99), stat.label, stat.key)))


def select_highlights(rows: Iterable[tuple[str, float]], limit: int = 3) -> tuple[ItemStat, ...]:
    candidates = [stat for stat in format_stats(rows) if stat.priority is not None]
    candidates.sort(key=lambda stat: (stat.priority or 999, -abs(stat.value), stat.label))
    return tuple(candidates[: max(0, min(limit, 5))])
