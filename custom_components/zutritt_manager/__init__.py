from __future__ import annotations

import hashlib
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant, Event, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN
from .storage import ZutrittStorage
from .websocket import async_register_ws

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch"]

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _norm(s: str) -> str:
    return (s or "").strip().lower()

def _hash_pin(salt: str, pin: str) -> str:
    return hashlib.sha256((salt + pin).encode("utf-8")).hexdigest()

def _normalize_groups(groups) -> list[str]:
    """Normalize groups to entity-id-safe slugs."""
    if not groups:
        return []
    out: list[str] = []
    for g in groups:
        if not isinstance(g, str):
            continue
        s = g.strip().lower()
        if not s:
            continue
        s = " ".join(s.split())
        s = s.replace(",", "")
        s = s.replace(" ", "_")
        s = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in s)
        while "__" in s:
            s = s.replace("__", "_")
        s = s.strip("_")
        if s:
            out.append(s)
    return out

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    # -----------------------------
    # Storage + WS
    # -----------------------------
    storage = ZutrittStorage(hass)
    await storage.async_load()
    hass.data.setdefault(DOMAIN, {})["storage"] = storage

    async_register_ws(hass)
    # -----------------------------
    # Deine bestehende Logik (Events -> prüfen -> loggen -> pulse)
    # -----------------------------
    async def _pulse_input_boolean(entity_id: str, seconds: float = 0.35) -> None:
        await hass.services.async_call(
            "input_boolean", "turn_on", {"entity_id": entity_id}, blocking=False
        )

        @callback
        def _off(_):
            hass.async_create_task(
                hass.services.async_call(
                    "input_boolean", "turn_off", {"entity_id": entity_id}, blocking=False
                )
            )

        async_call_later(hass, timedelta(seconds=seconds), _off)

    async def _pulse_group_switches(groups: list[str]) -> None:
        for g in _normalize_groups(groups):
            entity_id = f"switch.zutritt_gruppe_{g}"
            await hass.services.async_call(
                "switch", "turn_on", {"entity_id": entity_id}, blocking=False
            )

    async def _on_esphome_input(ev: Event) -> None:
        d = ev.data or {}
        source = (d.get("source") or "unknown").strip()
        typ = _norm(d.get("type") or "")
        value = str(d.get("value") or "").strip()

        st = storage.get_state() or {}
        users = st.get("users") or []
        if not isinstance(users, list):
            users = []

        user = None
        if typ == "pin":
            for u in users:
                if not u.get("enabled", True):
                    continue
                salt = u.get("salt") or ""
                hashes = u.get("pin_hashes") or []
                if salt and hashes and value:
                    if _hash_pin(salt, value) in hashes:
                        user = u
                        break

        elif typ == "rfid":
            for u in users:
                if not u.get("enabled", True):
                    continue
                rfids = u.get("rfids") or []
                if value and value in [str(x).strip() for x in rfids]:
                    user = u
                    break

        granted = user is not None
        uname = (user.get("name") if user else "-") or "-"
        groups = _normalize_groups(user.get("groups", [])) if user else []

        event_data = {
            "source": source,
            "type": typ or "unknown",
            "result": "granted" if granted else "denied",
            "user": uname,
            "groups": groups,
        }

        # Zentrales Event (Automationen/GUI)
        hass.bus.async_fire("zutritt_manager.access", event_data)

        # Backend Log (immer)
        await storage.async_append_log(event_data)

        # Feedback Helper (wenn vorhanden)
        if granted:
            await _pulse_input_boolean("input_boolean.halle_keypad_granted")
            await _pulse_group_switches(groups)
        else:
            await _pulse_input_boolean("input_boolean.halle_keypad_denied")

    hass.bus.async_listen("esphome.zutritt_input", _on_esphome_input)

    return True


from homeassistant.config_entries import ConfigEntry

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Zutritt Manager from a config entry."""
    # Ensure async_setup ran and storage exists
    hass.data.setdefault(DOMAIN, {})
    if "storage" not in hass.data[DOMAIN]:
        storage = ZutrittStorage(hass)
        await storage.async_load()
        hass.data[DOMAIN]["storage"] = storage
        async_register_ws(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
