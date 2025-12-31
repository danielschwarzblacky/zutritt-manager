from __future__ import annotations

import hashlib
from datetime import timedelta

from homeassistant.core import HomeAssistant, Event, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN
from .storage import ZutrittStorage
from .websocket import async_register_ws

PLATFORMS = ["switch"]


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _hash_pin(salt: str, pin: str) -> str:
    return hashlib.sha256((salt + pin).encode("utf-8")).hexdigest()


def _normalize_groups(groups) -> list[str]:
    if not groups:
        return []
    out = []
    for g in groups:
        if isinstance(g, str) and g.strip():
            out.append(g.strip().lower())
    return out


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    storage = ZutrittStorage(hass)
    await storage.async_load()
    hass.data.setdefault(DOMAIN, {})["storage"] = storage

    async_register_ws(hass)

    async def _pulse_input_boolean(entity_id: str, seconds: float = 0.35) -> None:
        # ON
        await hass.services.async_call(
            "input_boolean", "turn_on", {"entity_id": entity_id}, blocking=False
        )

        # OFF später
        @callback
        def _off(_):
            hass.async_create_task(
                hass.services.async_call(
                    "input_boolean", "turn_off", {"entity_id": entity_id}, blocking=False
                )
            )

        async_call_later(hass, timedelta(seconds=seconds), _off)

    async def _pulse_group_switches(groups: list[str]) -> None:
        # Wichtig: NICHT über Entity-Objekte, sondern über Service auf Entity-ID
        for g in _normalize_groups(groups):
            entity_id = f"switch.zutritt_gruppe_{g}"
            await hass.services.async_call(
                "switch", "turn_on", {"entity_id": entity_id}, blocking=False
            )
            # unsere SwitchEntity setzt sich selbst wieder aus (Impuls)
            # falls du doch OFF erzwingen willst, hier optional:
            # async_call_later(... switch.turn_off ...)

    # ------------------------------------------------------------
    # 24/7: ESPHome sendet Rohdaten -> prüfen -> access event -> log + group pulse
    # ------------------------------------------------------------
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

        # Backend Log (immer, unabhängig von UI)
        await storage.async_append_log(event_data)

        # Feedback an ESP (wenn du die helper hast)
        if granted:
            await _pulse_input_boolean("input_boolean.halle_keypad_granted")
            await _pulse_group_switches(groups)
        else:
            await _pulse_input_boolean("input_boolean.halle_keypad_denied")

    hass.bus.async_listen("esphome.zutritt_input", _on_esphome_input)

    # ------------------------------------------------------------
    # 24/7: Wenn irgendwer direkt zutritt_manager.access feuert -> log + group pulse
    # (damit deine manuellen Tests ohne Hardware auch Puls + Log erzeugen)
    # ------------------------------------------------------------
    async def _on_access(ev: Event) -> None:
        d = ev.data or {}
        result = _norm(d.get("result") or "")
        groups = _normalize_groups(d.get("groups") or [])

        # Backend Log (auch wenn das Event nicht von uns kommt)
        await storage.async_append_log(
            {
                "source": d.get("source", "unknown"),
                "type": d.get("type", "unknown"),
                "result": d.get("result", "unknown"),
                "user": d.get("user", "-"),
                "groups": groups,
            }
        )

        if result == "granted":
            await _pulse_group_switches(groups)

    hass.bus.async_listen("zutritt_manager.access", _on_access)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
