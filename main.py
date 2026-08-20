import asyncio
import sys
from pathlib import Path

import decky

PLUGIN_ROOT = Path(__file__).resolve().parent
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from backend.controller import GdiaController, InventoryError


class Plugin:
    def __init__(self, controller=None):
        self._controller = controller or GdiaController()

    async def _main(self):
        decky.logger.info("Grim Dawn Item Assistant Decky controller loaded")

    async def _unload(self):
        decky.logger.info("Grim Dawn Item Assistant Decky controller unloaded")

    async def get_status(self):
        try:
            status = await asyncio.to_thread(self._controller.status)
            return status.to_dict()
        except Exception:
            decky.logger.exception("Status request failed")
            return {
                "installed": False,
                "databaseReady": False,
                "itemCount": 0,
                "itemAssistantRunning": False,
                "grimDawnRunning": False,
                "bridgeReady": False,
                "bridgeVersion": None,
                "message": "Could not inspect Item Assistant",
            }

    async def search_items(self, filters=None):
        try:
            result = await asyncio.to_thread(self._controller.search, filters)
            return result.to_dict()
        except InventoryError as exc:
            decky.logger.warning("Inventory search unavailable: %s", exc)
            return {
                "items": [],
                "total": 0,
                "offset": 0,
                "limit": 30,
                "hasMore": False,
                "error": str(exc),
            }
        except Exception:
            decky.logger.exception("Inventory search failed")
            return {
                "items": [],
                "total": 0,
                "offset": 0,
                "limit": 30,
                "hasMore": False,
                "error": "Could not search Item Assistant",
            }

    async def transfer_item(self, player_item_id):
        try:
            result = await asyncio.to_thread(
                self._controller.transfer, player_item_id
            )
            decky.logger.info(
                "Item transfer finished: ok=%s uncertain=%s",
                result.ok,
                result.uncertain,
            )
            return result.to_dict()
        except Exception:
            decky.logger.exception("Item transfer failed")
            return {
                "ok": False,
                "message": "Unexpected Item Assistant bridge error",
                "uncertain": False,
            }

    async def get_item_details(self, player_item_id):
        try:
            details = await asyncio.to_thread(
                self._controller.details, player_item_id
            )
            return details.to_dict() if details is not None else None
        except Exception:
            decky.logger.exception("Item details request failed")
            return None

    async def list_characters(self):
        try:
            characters = await asyncio.to_thread(self._controller.list_characters)
            return [character.to_dict() for character in characters]
        except Exception:
            decky.logger.exception("Character list request failed")
            return []
