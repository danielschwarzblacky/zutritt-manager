import hashlib, secrets
from homeassistant.components import websocket_api
from .const import DOMAIN

def _hash(salt, pin):
    return hashlib.sha256((salt + pin).encode()).hexdigest()

def async_register_ws(hass):

    @websocket_api.websocket_command({"type": "zutritt_manager/get_state"})
    async def get_state(hass, conn, msg):
        conn.send_result(msg["id"], hass.data[DOMAIN]["storage"].get_state())

    @websocket_api.websocket_command(
        {"type": "zutritt_manager/add_user", "name": str}
    )
    async def add_user(hass, conn, msg):
        st = hass.data[DOMAIN]["storage"].state
        st["users"].append({
            "id": secrets.token_hex(8),
            "name": msg["name"],
            "enabled": True,
            "groups": [],
            "rfids": [],
            "salt": secrets.token_hex(8),
            "pin_hashes": []
        })
        await hass.data[DOMAIN]["storage"].async_save()
        conn.send_result(msg["id"], True)

    websocket_api.async_register_command(hass, get_state)
    websocket_api.async_register_command(hass, add_user)
