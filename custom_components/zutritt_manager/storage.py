from __future__ import annotations

import json
import time
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

LOG_RETENTION_DAYS = 30
LOG_FILE = "/config/www/zutritt_manager_access.log"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _default_state() -> dict[str, Any]:
    return {
        "users": [],
        "sources": {},
        "group_booleans": {},
        "log": [],
    }


class ZutrittStorage:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.state: dict[str, Any] = _default_state()

        # Dedup: doppelte identische Events im kurzen Zeitfenster ignorieren
        self._dedup_window_s = 0.8
        self._dedup_last_sig: str | None = None
        self._dedup_last_ts: float = 0.0

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

            sources = data.get("sources")
            if isinstance(sources, dict):
                self.state["sources"] = sources

            group_booleans = data.get("group_booleans")
            if isinstance(group_booleans, dict):
                self.state["group_booleans"] = group_booleans

            # Log migrieren wir bewusst NICHT (sonst doppelt + unnötig groß)
            return True

        return False

    async def async_save(self) -> None:
        await self.store.async_save(self.state)

    def get_state(self) -> dict[str, Any]:
        return self.state

    def get_groups(self) -> list[str]:
        """Return normalized group ids.

        Uses state['groups'] when present (UI-managed) and also derives from user entries.
        Normalization makes ids entity_id-safe: lowercase, spaces -> underscore, strip punctuation.
        Falls back to the legacy default groups if nothing is defined.
        """
        st = self.state or {}

        def _slug(g: str) -> str:
            g = (g or "").strip().lower()
            g = " ".join(g.split())
            g = g.replace(",", "")
            g = g.replace(" ", "_")
            g = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in g)
            while "__" in g:
                g = g.replace("__", "_")
            return g.strip("_")

        out: list[str] = []

        raw_groups = st.get("groups", [])
        if isinstance(raw_groups, list):
            for g in raw_groups:
                sg = _slug(str(g))
                if sg:
                    out.append(sg)

        users = st.get("users", [])
        if isinstance(users, list):
            for u in users:
                for g in (u.get("groups") or []):
                    sg = _slug(str(g))
                    if sg:
                        out.append(sg)

        if not out:
            out = ["chef", "lieferant", "mitarbeiter"]

        return sorted(set(out))

    def get_log(self) -> list[dict[str, Any]]:
        lg = self.state.get("log", [])
        return lg if isinstance(lg, list) else []

    async def async_clear_log(self) -> None:
        self.state["log"] = []
        await self.async_save()

    async def async_prune_logs(self) -> None:
        cutoff = _utc_now() - timedelta(days=LOG_RETENTION_DAYS)
        new_log: list[dict[str, Any]] = []

        for e in self.get_log():
            try:
                t = datetime.fromisoformat(e.get("time"))
                if t >= cutoff:
                    new_log.append(e)
            except Exception:
                # kaputte Zeilen ignorieren
                pass

        self.state["log"] = new_log
        await self.async_save()

    async def async_append_log(self, entry: dict[str, Any]) -> None:
        # Zeit setzen (ISO8601)
        entry["time"] = _utc_now().isoformat()

        # ✅ Dedup MUSS VOR dem Einfügen passieren
        now = time.monotonic()
        sig_obj = {k: entry.get(k) for k in entry.keys() if k != "time"}
        sig = json.dumps(sig_obj, sort_keys=True, ensure_ascii=False, default=str)

        if self._dedup_last_sig == sig and (now - self._dedup_last_ts) <= self._dedup_window_s:
            return

        self._dedup_last_sig = sig
        self._dedup_last_ts = now

        # RAM-Log
        lg = self.state.setdefault("log", [])
        if not isinstance(lg, list):
            lg = []
            self.state["log"] = lg

        lg.insert(0, entry)

        # Retention
        await self.async_prune_logs()

        # Datei schreiben (blocking -> executor)
        await self.hass.async_add_executor_job(self._append_file, entry)

    def _append_file(self, entry: dict[str, Any]) -> None:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except Exception:
            # keine Exceptions nach oben werfen (sonst nervt es die Integration)
            pass
