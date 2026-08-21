from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.inventory import InventoryRepository

from .helpers import create_inventory_database


class InventoryRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database = self.root / "userdata.db"
        create_inventory_database(self.database)
        self.repository = InventoryRepository(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_validates_schema_and_counts_only_stored_items(self) -> None:
        self.assertTrue(self.repository.validate())
        self.assertEqual(self.repository.item_count(), 4)

    def test_search_filters_mode_rarity_level_and_sort(self) -> None:
        result = self.repository.search(
            {
                "rarity": "Green",
                "mode": "hardcore",
                "minimumLevel": 40,
                "maximumLevel": 60,
                "sort": "level_desc",
            }
        )
        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0].name, "Verdant Claw")
        self.assertTrue(result.items[0].hardcore)
        self.assertEqual(result.items[0].stack_count, 2)

    def test_search_escapes_sql_wildcards(self) -> None:
        percent = self.repository.search({"query": "%"})
        underscore = self.repository.search({"query": "_"})
        self.assertEqual([item.name for item in percent.items], ["100% Proof"])
        self.assertEqual([item.name for item in underscore.items], ["Aether_Blade"])

    def test_search_treats_injection_text_as_literal(self) -> None:
        result = self.repository.search({"query": "%' OR 1=1 --"})
        self.assertEqual(result.total, 0)
        self.assertEqual(result.items, [])
        with closing(sqlite3.connect(self.database)) as connection:
            count = connection.execute("SELECT count(*) FROM PlayerItem").fetchone()[0]
        self.assertEqual(count, 5)

    def test_invalid_filters_fall_back_to_bounded_defaults(self) -> None:
        result = self.repository.search(
            {
                "rarity": "DELETE FROM PlayerItem",
                "mode": "anything",
                "sort": "random()",
                "minimumLevel": 100,
                "maximumLevel": 0,
                "offset": -9,
                "limit": 999,
            }
        )
        self.assertEqual(result.total, 4)
        self.assertEqual(result.offset, 0)
        self.assertEqual(result.limit, 50)

    def test_get_item_rejects_boolean_and_missing_items(self) -> None:
        self.assertIsNone(self.repository.get_item(True))
        self.assertIsNone(self.repository.get_item(-1))
        self.assertIsNone(self.repository.get_item(4))
        self.assertEqual(self.repository.get_item(1).name, "Aetherfire")

    def test_search_includes_three_high_value_stat_summaries(self) -> None:
        item = self.repository.search({"query": "Aetherfire"}).items[0]
        self.assertEqual(item.slot, "Chest Armor")
        self.assertEqual(
            [stat.display_value for stat in item.highlights],
            ["812 Armor", "+74 Offensive Ability", "+28% Aether Resistance"],
        )
        self.assertNotIn("__computed__", [stat.key for stat in item.highlights])

    def test_details_include_all_formatted_stats_and_storage_time(self) -> None:
        details = self.repository.get_details(1)
        self.assertIsNotNone(details)
        assert details is not None
        self.assertEqual(details.item.slot, "Chest Armor")
        self.assertEqual(len(details.stats), 7)
        self.assertEqual(details.item.stored_at, "2026-01-01T00:00:00Z")
        self.assertEqual(details.stats[-1].display_value, "+102% Aether Damage")
        self.assertEqual(
            [bonus.display_value for bonus in details.item.build_bonuses],
            [
                "+2 to all skills in Arcanist",
                "+3 to Iskandra's Elemental Exchange",
                "Grants Aether Nova",
            ],
        )

    def test_filters_by_slot_and_resistance_contribution(self) -> None:
        result = self.repository.search(
            {
                "slot": "ArmorProtective_Chest",
                "resistance": "fire",
                "minimumResistance": 25,
                "sort": "resistance_desc",
            }
        )
        self.assertEqual([item.name for item in result.items], ["Aetherfire"])
        self.assertEqual(result.items[0].match_reasons[0], "+27% Fire Resistance")

    def test_filters_by_mastery_and_specific_skill_bonus(self) -> None:
        mastery = self.repository.search({"mastery": "class05"})
        skill = self.repository.search(
            {"mastery": "class05", "skill": "Iskandra's Elemental Exchange"}
        )
        self.assertEqual([item.name for item in mastery.items], ["Aetherfire"])
        self.assertEqual([item.name for item in skill.items], ["Aetherfire"])
        self.assertIn("+3 to Iskandra's Elemental Exchange", skill.items[0].match_reasons)

    def test_lists_masteries_and_skills_from_item_database(self) -> None:
        options = self.repository.build_options()
        self.assertEqual(
            [(mastery.mastery_id, mastery.name) for mastery in options.masteries],
            [("class05", "Arcanist"), ("class04", "Nightblade")],
        )
        self.assertEqual(
            [(skill.name, skill.mastery_id) for skill in options.skills],
            [("Iskandra's Elemental Exchange", "class05")],
        )

    def test_invalid_build_selectors_are_ignored_and_contribution_is_bounded(self) -> None:
        result = self.repository.search(
            {
                "slot": "DROP TABLE PlayerItem",
                "resistance": "anything",
                "minimumResistance": 999,
                "mastery": "class99",
                "skill": "fake skill",
                "sort": "resistance_desc",
            }
        )
        self.assertEqual(result.total, 0)


if __name__ == "__main__":
    unittest.main()
