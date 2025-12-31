from __future__ import annotations

from homeassistant import config_entries

from .const import DOMAIN


class ZutrittManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        # Nur eine Instanz erlauben
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        # Keine Optionen nötig -> direkt Entry erstellen
        return self.async_create_entry(title="Zutritt Manager", data={})
