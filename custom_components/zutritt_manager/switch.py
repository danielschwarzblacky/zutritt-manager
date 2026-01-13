from __future__ import annotations

from datetime import timedelta

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN, SIGNAL_GROUPS_UPDATED, IMPULSE_SECONDS


class ZutrittGroupSwitch(SwitchEntity):
    """Momentary group switch.

    Turns ON briefly (IMPULSE_SECONDS) and then automatically turns OFF.
    Used by the core logic in __init__.py to trigger group based automations.
    """

    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, group: str) -> None:
        self.hass = hass
        self.group = group
        # Keep naming stable -> entity_id becomes switch.zutritt_gruppe_<group>
        self._attr_name = f"Zutritt Gruppe {group}"
        self._attr_unique_id = f"{DOMAIN}_group_{group}"
        self._attr_icon = "mdi:account-key"
        self._is_on = False

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_turn_on(self, **kwargs) -> None:
        await self.async_impulse(int(IMPULSE_SECONDS))

    async def async_turn_off(self, **kwargs) -> None:
        self._is_on = False
        self.async_write_ha_state()

    async def async_impulse(self, seconds: int) -> None:
        self._is_on = True
        self.async_write_ha_state()

        @callback
        def _off(_now):
            self._is_on = False
            self.async_write_ha_state()

        async_call_later(self.hass, timedelta(seconds=max(1, int(seconds))), _off)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create one switch entity per group in storage, and update dynamically."""
    storage = hass.data.get(DOMAIN, {}).get("storage")
    if storage is None:
        return

    entities: list[ZutrittGroupSwitch] = []

    def _add_missing_groups() -> None:
        groups = []
        try:
            groups = storage.get_groups()
        except Exception:
            # fall back to previous behavior
            groups = ["chef", "lieferant", "mitarbeiter"]

        existing = {e.group for e in entities}
        new_entities: list[ZutrittGroupSwitch] = []
        for g in groups:
            if not g or g in existing:
                continue
            sw = ZutrittGroupSwitch(hass, g)
            entities.append(sw)
            new_entities.append(sw)

        if new_entities:
            async_add_entities(new_entities, update_before_add=False)

    # initial add
    _add_missing_groups()

    # add new groups on demand (created via UI/websocket)
    async_dispatcher_connect(hass, SIGNAL_GROUPS_UPDATED, _add_missing_groups)
