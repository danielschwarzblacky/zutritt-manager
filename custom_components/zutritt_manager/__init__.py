from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.components import frontend

from .const import DOMAIN, PANEL_URL, PANEL_TITLE, PANEL_ICON
from .storage import ZutrittStorage
from .websocket import async_register_ws


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    # Storage laden
    storage = ZutrittStorage(hass)
    await storage.async_load()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["storage"] = storage

    # Websocket API registrieren
    async_register_ws(hass)

    # Sidebar Panel registrieren (JS kommt aus /config/www -> /local/)
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_URL,  # muss "zutritt" sein
        config={
            "name": "zutritt",
            "module_url": "/local/zutritt-panel.js",
        },
        require_admin=True,
    )

    return True
