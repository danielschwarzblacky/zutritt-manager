from homeassistant.helpers.event import async_track_event
from homeassistant.components import frontend
from .storage import ZutrittStorage
from .websocket import async_register_ws
from .const import DOMAIN, PANEL_URL, PANEL_TITLE, PANEL_ICON

async def async_setup(hass, config):
    storage = ZutrittStorage(hass)
    await storage.async_load()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["storage"] = storage

    async_register_ws(hass)

    import pathlib
    panel_path = pathlib.Path(__file__).parent / "panel"
    hass.http.register_static_path(
        "/api/zutritt_manager_panel",
        str(panel_path),
        cache_headers=False
    )

    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_URL,
        config={"module_url": "/api/zutritt_manager_panel/zutritt-panel.js"},
        require_admin=True,
    )

    return True
