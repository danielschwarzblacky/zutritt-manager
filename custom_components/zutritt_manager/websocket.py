from __future__ import annotations

import hashlib
import secrets

from homeassistant.components import websocket_api

from .const import DOMAIN


def _split_csv(s: str) -> list[str]:
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


def _hash_pin(salt: str, pin: str) -> str:
    return hashlib.sha256((salt + pin).encode("utf-8")).hexdigest()


def _get_storage(hass):
    return hass.data.get(DOMAIN, {}).get("storage")


def async_register_ws(hass):

    @websocket_api.websocket_command({"type": "zutritt_manager/get_state"})
    @websocket_api.async_response
    async def ws_get_state(hass, conn, msg):
        storage = _get_storage(hass)
        if not storage:
            conn.send_result(msg["id"], {"users": [], "sources": {}, "group_booleans": {}})
            return
        st = storage.get_state() or {}
        conn.send_result(
            msg["id"],
            {
                "users": st.get("users", []),
                "sources": st.get("sources", {}),
                "group_booleans": st.get("group_booleans", {}),
            },
        )

    @websocket_api.websocket_command({"type": "zutritt_manager/get_log"})
    @websocket_api.async_response
    async def ws_get_log(hass, conn, msg):
        storage = _get_storage(hass)
        if not storage:
            conn.send_result(msg["id"], {"log": []})
            return
        conn.send_result(msg["id"], {"log": storage.get_log()})

    @websocket_api.websocket_command({"type": "zutritt_manager/clear_log"})
    @websocket_api.async_response
    async def ws_clear_log(hass, conn, msg):
        storage = _get_storage(hass)
        if storage:
            await storage.async_clear_log()
        conn.send_result(msg["id"], True)

    @websocket_api.websocket_command({"type": "zutritt_manager/add_user", "name": str})
    @websocket_api.async_response
    async def ws_add_user(hass, conn, msg):
        storage = _get_storage(hass)
        if not storage:
            conn.send_error(msg["id"], "not_ready", "storage not initialized")
            return

        st = storage.state
        users = st.setdefault("users", [])

        user = {
            "id": secrets.token_hex(8),
            "name": (msg["name"].strip() or "Ohne Name"),
            "enabled": True,
            "groups": [],
            "rfids": [],
            "salt": secrets.token_hex(8),
            "pin_hashes": [],
        }
        users.append(user)

        await storage.async_save()
        conn.send_result(msg["id"], True)

    @websocket_api.websocket_command(
        {
            "type": "zutritt_manager/update_user",
            "user_id": str,
            "name": str,
            "enabled": bool,
            "groups_csv": str,
            "rfids_csv": str,
            "pins_csv": str,
        }
    )
    @websocket_api.async_response
    async def ws_update_user(hass, conn, msg):
        storage = _get_storage(hass)
        if not storage:
            conn.send_error(msg["id"], "not_ready", "storage not initialized")
            return

        st = storage.state
        users = st.setdefault("users", [])

        uid = msg["user_id"]
        u = next((x for x in users if x.get("id") == uid), None)
        if not u:
            conn.send_error(msg["id"], "not_found", f"user_id {uid} not found")
            return

        u["name"] = msg["name"].strip() or u.get("name") or "Ohne Name"
        u["enabled"] = bool(msg["enabled"])
        u["groups"] = _split_csv(msg.get("groups_csv", ""))
        u["rfids"] = _split_csv(msg.get("rfids_csv", ""))

        pins_csv = (msg.get("pins_csv") or "").strip()
        if pins_csv and pins_csv != "__KEEP__":
            if pins_csv.lower() == "clear":
                u["pin_hashes"] = []
            else:
                pins = _split_csv(pins_csv)
                salt = u.get("salt") or secrets.token_hex(8)
                u["salt"] = salt
                u["pin_hashes"] = [_hash_pin(salt, p) for p in pins]

        await storage.async_save()
        conn.send_result(msg["id"], True)

    @websocket_api.websocket_command({"type": "zutritt_manager/delete_user", "user_id": str})
    @websocket_api.async_response
    async def ws_delete_user(hass, conn, msg):
        storage = _get_storage(hass)
        if not storage:
            conn.send_error(msg["id"], "not_ready", "storage not initialized")
            return

        st = storage.state
        users = st.setdefault("users", [])

        uid = msg["user_id"]
        before = len(users)
        users[:] = [u for u in users if u.get("id") != uid]
        if len(users) == before:
            conn.send_error(msg["id"], "not_found", f"user_id {uid} not found")
            return

        await storage.async_save()
        conn.send_result(msg["id"], True)

    @websocket_api.websocket_command(
        {"type": "zutritt_manager/set_config", "sources": dict, "group_booleans": dict}
    )
    @websocket_api.async_response
    async def ws_set_config(hass, conn, msg):
        storage = _get_storage(hass)
        if not storage:
            conn.send_error(msg["id"], "not_ready", "storage not initialized")
            return

        st = storage.state
        st["sources"] = msg.get("sources") or {}
        st["group_booleans"] = msg.get("group_booleans") or {}
        await storage.async_save()
        conn.send_result(msg["id"], True)

    websocket_api.async_register_command(hass, ws_get_state)
    websocket_api.async_register_command(hass, ws_get_log)
    websocket_api.async_register_command(hass, ws_clear_log)
    websocket_api.async_register_command(hass, ws_add_user)
    websocket_api.async_register_command(hass, ws_update_user)
    websocket_api.async_register_command(hass, ws_delete_user)
    websocket_api.async_register_command(hass, ws_set_config)
