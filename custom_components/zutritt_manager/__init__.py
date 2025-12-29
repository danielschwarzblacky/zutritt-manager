from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.components import frontend

from .const import DOMAIN, PANEL_URL, PANEL_TITLE, PANEL_ICON, EVENT_ZUTRITT, EVENT_BELL
from .storage import ZutrittStorage
from .websocket import async_register_ws

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    storage = ZutrittStorage(hass)
    await storage.async_load()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["storage"] = storage
    hass.data[DOMAIN].setdefault("unsubs", [])

    async_register_ws(hass)

    # Panel JS ausliefern
    import pathlib
    panel_path = pathlib.Path(__file__).parent / "panel"
    hass.http.register_static_path(
        "/api/zutritt_manager_panel",
        str(panel_path),
        cache_headers=False,
    )

    # Sidebar Panel registrieren
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_URL,
        config={"module_url": "/api/zutritt_manager_panel/zutritt-panel.js"},
        require_admin=True,
    )

    # Event Listener (ohne async_track_event)
    def on_zutritt(event):
        # später: Zutrittslogik
        return

    def on_bell(event):
        # später: Klingel-Logik
        return

    hass.data[DOMAIN]["unsubs"].append(hass.bus.async_listen(EVENT_ZUTRITT, on_zutritt))
    hass.data[DOMAIN]["unsubs"].append(hass.bus.async_listen(EVENT_BELL, on_bell))

    return True
