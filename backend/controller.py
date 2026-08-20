from __future__ import annotations

from typing import Callable

from .bridge import BridgeClient
from .characters import CharacterRepository
from .inventory import InventoryError, InventoryRepository
from .models import CharacterSummary, ItemDetails, OperationResult, PluginStatus, SearchResult
from .paths import GdiaPaths
from .processes import any_process_named


class GdiaController:
    def __init__(
        self,
        paths: GdiaPaths | None = None,
        inventory: InventoryRepository | None = None,
        bridge: BridgeClient | None = None,
        characters: CharacterRepository | None = None,
        process_checker: Callable[[str], bool] | None = None,
    ):
        self.paths = paths or GdiaPaths.discover()
        self.inventory = inventory or InventoryRepository(self.paths.database)
        self.bridge = bridge or BridgeClient(self.paths)
        self.characters = characters or CharacterRepository(self.paths.steam_root)
        self._process_checker = process_checker or any_process_named

    def status(self) -> PluginStatus:
        installed = (self.paths.item_assistant_dir / "IAGrim.exe").is_file()
        database_ready = self.inventory.validate()
        item_count = self.inventory.item_count() if database_ready else 0
        item_assistant_running = self._process_checker("IAGrim.exe")
        grim_dawn_running = self._process_checker("Grim Dawn.exe")
        bridge_ready, bridge_version = self.bridge.status()

        if not installed:
            message = "Item Assistant is not installed in Grim Dawn's Proton prefix"
        elif not database_ready:
            message = "Item Assistant's inventory database is not ready"
        elif not item_assistant_running:
            message = "Launch Grim Dawn to start Item Assistant"
        elif not bridge_ready:
            message = "Item Assistant is running without the Decky bridge"
        elif not grim_dawn_running:
            message = "Launch Grim Dawn to receive items"
        else:
            message = "Ready to send items to Grim Dawn"

        return PluginStatus(
            installed=installed,
            database_ready=database_ready,
            item_count=item_count,
            item_assistant_running=item_assistant_running,
            grim_dawn_running=grim_dawn_running,
            bridge_ready=bridge_ready,
            bridge_version=bridge_version,
            message=message,
        )

    def search(self, filters: dict | None) -> SearchResult:
        return self.inventory.search(filters)

    def details(self, player_item_id: int) -> ItemDetails | None:
        return self.inventory.get_details(player_item_id)

    def list_characters(self) -> tuple[CharacterSummary, ...]:
        return self.characters.list()

    def transfer(self, player_item_id: int) -> OperationResult:
        item = self.inventory.get_item(player_item_id)
        if item is None:
            return OperationResult(False, "That item is no longer in Item Assistant")
        return self.bridge.transfer(player_item_id)


__all__ = ["GdiaController", "InventoryError"]
