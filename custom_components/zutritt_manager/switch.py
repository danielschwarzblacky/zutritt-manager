from __future__ import annotations

from datetime import timedelta

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN

DEFAULT_GROUPS = ["chef", "lieferant", "mitarbeiter"]
IMPULSE_SECONDS = 2


class ZutrittGroupSwitch(SwitchEntity):
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, group: str) -> None:
        self.hass = hass
        self.group = group
        self._attr_name = f"Zutritt Gruppe {group.capitalize()}"
        self._attr_unique_id = f"{DOMAIN}_group_{group}"
        self._attr_icon = "mdi:account-key"
        self._is_on = False

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_turn_on(self, **kwargs) -> None:
        await self.async_impulse(IMPULSE_SECONDS)

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

        async_call_later(self.hass, timedelta(seconds=seconds), _off)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    # Fixe Gruppen, damit die Entity-IDs immer existieren
    entities = [ZutrittGroupSwitch(hass, g) for g in DEFAULT_GROUPS]
    async_add_entities(entities, update_before_add=False)
