from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.controller import GdiaController
from backend.models import InventoryItem, ItemDetails, ItemStat, OperationResult

from .helpers import make_paths


class FakeInventory:
    def __init__(self, item: InventoryItem | None = None):
        self.item = item

    def validate(self) -> bool:
        return True

    def item_count(self) -> int:
        return 42

    def get_item(self, player_item_id: int) -> InventoryItem | None:
        if self.item and self.item.player_item_id == player_item_id:
            return self.item
        return None

    def get_details(self, player_item_id: int) -> ItemDetails | None:
        if self.item and self.item.player_item_id == player_item_id:
            return ItemDetails(
                self.item,
                (ItemStat("characterLife", "Health", 100, "+100 Health", "Defense"),),
            )
        return None


class FakeBridge:
    def __init__(self, ready: bool = True):
        self.ready = ready
        self.transferred: list[int] = []

    def status(self) -> tuple[bool, int | None]:
        return self.ready, 1 if self.ready else None

    def transfer(self, player_item_id: int) -> OperationResult:
        self.transferred.append(player_item_id)
        return OperationResult(True, "Transferred")


class ControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.paths = make_paths(Path(self.temporary_directory.name))
        self.paths.item_assistant_dir.mkdir(parents=True)
        (self.paths.item_assistant_dir / "IAGrim.exe").write_bytes(b"test")
        self.item = InventoryItem(7, "Test item", "Blue", 50, False, "", 1)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_ready_status_requires_item_assistant_game_and_bridge(self) -> None:
        running = {"IAGrim.exe", "Grim Dawn.exe"}
        controller = GdiaController(
            paths=self.paths,
            inventory=FakeInventory(self.item),
            bridge=FakeBridge(),
            process_checker=lambda name: name in running,
        )
        status = controller.status()
        self.assertTrue(status.bridge_ready)
        self.assertTrue(status.grim_dawn_running)
        self.assertEqual(status.item_count, 42)
        self.assertEqual(status.message, "Ready to send items to Grim Dawn")

    def test_status_explains_when_game_is_not_running(self) -> None:
        controller = GdiaController(
            paths=self.paths,
            inventory=FakeInventory(self.item),
            bridge=FakeBridge(),
            process_checker=lambda name: name == "IAGrim.exe",
        )
        self.assertEqual(controller.status().message, "Launch Grim Dawn to receive items")

    def test_transfer_checks_read_only_inventory_before_bridge(self) -> None:
        bridge = FakeBridge()
        controller = GdiaController(
            paths=self.paths,
            inventory=FakeInventory(self.item),
            bridge=bridge,
            process_checker=lambda name: False,
        )
        self.assertFalse(controller.transfer(999).ok)
        self.assertEqual(bridge.transferred, [])
        self.assertTrue(controller.transfer(7).ok)
        self.assertEqual(bridge.transferred, [7])

    def test_details_returns_enriched_item_without_using_bridge(self) -> None:
        bridge = FakeBridge()
        controller = GdiaController(
            paths=self.paths,
            inventory=FakeInventory(self.item),
            bridge=bridge,
            process_checker=lambda name: False,
        )
        details = controller.details(7)
        self.assertIsNotNone(details)
        assert details is not None
        self.assertEqual(details.stats[0].display_value, "+100 Health")
        self.assertEqual(bridge.transferred, [])


if __name__ == "__main__":
    unittest.main()
