from __future__ import annotations

import unittest

from backend.stats import format_stat, select_highlights


class StatFormattingTests(unittest.TestCase):
    def test_formats_common_defense_offense_and_utility_stats(self) -> None:
        self.assertEqual(format_stat("characterLife", 1421).display_value, "+1,421 Health")
        self.assertEqual(format_stat("skillCooldownReduction", 7.5).display_value, "-7.5% Skill Cooldown")
        self.assertEqual(format_stat("characterAttackSpeedModifier", 12).display_value, "+12% Attack Speed")

    def test_highlights_are_bounded_and_exclude_internal_marker(self) -> None:
        highlights = select_highlights(
            [
                ("__computed__", 1),
                ("offensiveFireModifier", 90),
                ("characterLife", 400),
                ("characterDefensiveAbility", 55),
                ("defensiveChaos", 23),
            ]
        )
        self.assertEqual(len(highlights), 3)
        self.assertNotIn("__computed__", [stat.key for stat in highlights])


if __name__ == "__main__":
    unittest.main()
