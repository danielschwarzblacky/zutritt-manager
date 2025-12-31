from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.store"

# Migration: alte mögliche Dateien
LEGACY_KEYS = [
    DOMAIN,
    f"{DOMAIN}.storage",
    f"{DOMAIN}.data",
]

LOG_RETENTION_DAYS = 21
LOG_FILE = "/config/zutritt_manager_access.log"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _default_state() -> dict[str, Any]:
    return {"users": [], "sources": {}, "group_booleans": {}, "log": []}


class ZutrittStorage:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.state: dict[str, Any] = _default_state()

    async def async_load(self) -> None:
        data = await self.store.async_load()
        if isinstance(data, dict):
            st = _default_state()
            st.update(data)
            st.setdefault("users", [])
            st.setdefault("log", [])
            self.state = st
        else:
            self.state = _default_state()

        # Migration nur wenn keine Users im neuen Store sind
        if not (self.state.get("users") or []):
            migrated = await self._try_migrate_from_legacy()
            if migrated:
                await self.async_save()

        await self.async_prune_logs()

    async def _try_migrate_from_legacy(self) -> bool:
        for key in LEGACY_KEYS:
            if key == STORAGE_KEY:
                continue
            legacy = Store(self.hass, STORAGE_VERSION, key)
            data = await legacy.async_load()
            if not isinstance(data, dict):
                continue
            users = data.get("users")
            if isinstance(users, list) and users:
                self.state["users"] = users
                if isinstance(data.get("sources"), dict):
                    self.state["sources"] = data["sources"]
                if isinstance(data.get("group_booleans"), dict):
                    self.state["group_booleans"] = data["group_booleans"]
                # Log migrieren wir bewusst NICHT
                return True
        return False

    async def async_save(self) -> None:
        await self.store.async_save(self.state)

    def get_state(self) -> dict[str, Any]:
        return self.state

    def get_log(self) -> list[dict[str, Any]]:
        lg = self.state.get("log", [])
        return lg if isinstance(lg, list) else []

    async def async_clear_log(self) -> None:
        self.state["log"] = []
        await self.async_save()

    async def async_prune_logs(self) -> None:
        cutoff = _utc_now() - timedelta(days=LOG_RETENTION_DAYS)
        new_log = []
        for e in self.get_log():
            try:
                t = datetime.fromisoformat(e.get("time"))
                if t >= cutoff:
                    new_log.append(e)
            except Exception:
                pass
        self.state["log"] = new_log
        await self.async_save()

    async def async_append_log(self, entry: dict[str, Any]) -> None:
        entry["time"] = _utc_now().isoformat()

        lg = self.state.setdefault("log", [])
        if not isinstance(lg, list):
            lg = []
            self.state["log"] = lg

        lg.insert(0, entry)

        await self.async_prune_logs()

        await self.hass.async_add_executor_job(self._append_file, entry)

    def _append_file(self, entry: dict[str, Any]) -> None:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
