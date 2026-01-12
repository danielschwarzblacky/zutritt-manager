from __future__ import annotations

import hashlib
import secrets

from homeassistant.components import websocket_api

from .const import DOMAIN


def _split_csv(s: str) -> list[str]:
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


def _norm_group(g: str) -> str:
    # erlaubt "Champions", "chef", "lieferant" usw.
    # trim, interne Mehrspaces weg, keine Kommas
    g = (g or "").strip()
    g = " ".join(g.split())
    g = g.replace(",", "")
    return g


def _hash_pin(salt: str, pin: str) -> str:
    return hashlib.sha256((salt + pin).encode("utf-8")).hexdigest()


def _get_storage(hass):
    return hass.data.get(DOMAIN, {}).get("storage")


def _ensure_base_state(st: dict) -> dict:
    st.setdefault("users", [])
    st.setdefault("sources", {})
    st.setdefault("group_booleans", {})
    st.setdefault("groups", [])  # ✅ zentrale Gruppenliste
    return st


def _sync_groups_from_users(st: dict) -> None:
    """Sammelt Gruppen aus Users ein und ergänzt st['groups']."""
    groups = st.setdefault("groups", [])
    known = set(groups)
    for u in st.get("users", []):
        for g in u.get("groups", []) or []:
            gg = _norm_group(g)
            if gg and gg not in known:
                known.add(gg)
                groups.append(gg)


def async_register_ws(hass):

    @websocket_api.websocket_command({"type": "zutritt_manager/get_state"})
    @websocket_api.async_response
    async def ws_get_state(hass, conn, msg):
        try:
            storage = _get_storage(hass)
            if not storage:
                conn.send_result(
                    msg["id"],
                    {"users": [], "sources": {}, "group_booleans": {}, "groups": []},
                )
                return

            st = _ensure_base_state(storage.state)
            _sync_groups_from_users(st)

            conn.send_result(
                msg["id"],
                {
                    "users": st.get("users", []),
                    "sources": st.get("sources", {}),
                    "group_booleans": st.get("group_booleans", {}),
                    "groups": st.get("groups", []),
                },
            )
        except Exception as e:
            conn.send_error(msg["id"], "get_state_failed", str(e))

    @websocket_api.websocket_command({"type": "zutritt_manager/add_user", "name": str})
    @websocket_api.async_response
    async def ws_add_user(hass, conn, msg):
        try:
            storage = _get_storage(hass)
            if not storage:
                conn.send_error(msg["id"], "not_ready", "storage not initialized")
                return

            st = _ensure_base_state(storage.state)
            users = st["users"]

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
        except Exception as e:
            conn.send_error(msg["id"], "add_user_failed", str(e))

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
        try:
            storage = _get_storage(hass)
            if not storage:
                conn.send_error(msg["id"], "not_ready", "storage not initialized")
                return

            st = _ensure_base_state(storage.state)
            users = st["users"]

            uid = msg["user_id"]
            u = next((x for x in users if x.get("id") == uid), None)
            if not u:
                conn.send_error(msg["id"], "not_found", f"user_id {uid} not found")
                return

            u["name"] = msg["name"].strip() or u.get("name") or "Ohne Name"
            u["enabled"] = bool(msg["enabled"])

            groups = [_norm_group(x) for x in _split_csv(msg.get("groups_csv", ""))]
            groups = [g for g in groups if g]
            u["groups"] = groups

            rfids = _split_csv(msg.get("rfids_csv", ""))
            u["rfids"] = rfids

            # PIN handling:
            # "__KEEP__" = nichts ändern
            # "clear"    = alle PINs löschen
            pins_csv = (msg.get("pins_csv") or "").strip()

            if pins_csv and pins_csv != "__KEEP__":
                if pins_csv.lower() == "clear":
                    u["pin_hashes"] = []
                else:
                    pins = _split_csv(pins_csv)
                    salt = u.get("salt") or secrets.token_hex(8)
                    u["salt"] = salt
                    u["pin_hashes"] = [_hash_pin(salt, p) for p in pins]

            # Gruppenliste automatisch pflegen (damit neue Gruppen sofort erscheinen)
            _sync_groups_from_users(st)

            await storage.async_save()
            conn.send_result(msg["id"], True)
        except Exception as e:
            conn.send_error(msg["id"], "update_user_failed", str(e))

    @websocket_api.websocket_command({"type": "zutritt_manager/delete_user", "user_id": str})
    @websocket_api.async_response
    async def ws_delete_user(hass, conn, msg):
        try:
            storage = _get_storage(hass)
            if not storage:
                conn.send_error(msg["id"], "not_ready", "storage not initialized")
                return

            st = _ensure_base_state(storage.state)
            users = st["users"]

            uid = msg["user_id"]
            before = len(users)
            users[:] = [u for u in users if u.get("id") != uid]
            if len(users) == before:
                conn.send_error(msg["id"], "not_found", f"user_id {uid} not found")
                return

            await storage.async_save()
            conn.send_result(msg["id"], True)
        except Exception as e:
            conn.send_error(msg["id"], "delete_user_failed", str(e))

    @websocket_api.websocket_command(
        {
            "type": "zutritt_manager/set_config",
            "sources": dict,
            "group_booleans": dict,
        }
    )
    @websocket_api.async_response
    async def ws_set_config(hass, conn, msg):
        try:
            storage = _get_storage(hass)
            if not storage:
                conn.send_error(msg["id"], "not_ready", "storage not initialized")
                return

            st = _ensure_base_state(storage.state)
            st["sources"] = msg.get("sources") or {}
            st["group_booleans"] = msg.get("group_booleans") or {}

            await storage.async_save()
            conn.send_result(msg["id"], True)
        except Exception as e:
            conn.send_error(msg["id"], "set_config_failed", str(e))

    # ✅ Gruppenverwaltung (genau was du willst)
    @websocket_api.websocket_command({"type": "zutritt_manager/get_groups"})
    @websocket_api.async_response
    async def ws_get_groups(hass, conn, msg):
        try:
            storage = _get_storage(hass)
            if not storage:
                conn.send_result(msg["id"], {"groups": []})
                return

            st = _ensure_base_state(storage.state)
            _sync_groups_from_users(st)
            conn.send_result(msg["id"], {"groups": st.get("groups", [])})
        except Exception as e:
            conn.send_error(msg["id"], "get_groups_failed", str(e))

    @websocket_api.websocket_command({"type": "zutritt_manager/add_group", "group": str})
    @websocket_api.async_response
    async def ws_add_group(hass, conn, msg):
        try:
            storage = _get_storage(hass)
            if not storage:
                conn.send_error(msg["id"], "not_ready", "storage not initialized")
                return

            st = _ensure_base_state(storage.state)
            g = _norm_group(msg.get("group", ""))
            if not g:
                conn.send_error(msg["id"], "invalid_group", "empty group")
                return

            groups = st.setdefault("groups", [])
            if g not in groups:
                groups.append(g)

            await storage.async_save()
            conn.send_result(msg["id"], True)
        except Exception as e:
            conn.send_error(msg["id"], "add_group_failed", str(e))

    @websocket_api.websocket_command({"type": "zutritt_manager/delete_group", "group": str})
    @websocket_api.async_response
    async def ws_delete_group(hass, conn, msg):
        try:
            storage = _get_storage(hass)
            if not storage:
                conn.send_error(msg["id"], "not_ready", "storage not initialized")
                return

            st = _ensure_base_state(storage.state)
            g = _norm_group(msg.get("group", ""))
            if not g:
                conn.send_error(msg["id"], "invalid_group", "empty group")
                return

            # aus Gruppenliste entfernen
            groups = st.setdefault("groups", [])
            groups[:] = [x for x in groups if _norm_group(x) != g]

            # ✅ bei allen Usern entfernen
            for u in st.get("users", []):
                ug = u.get("groups", []) or []
                u["groups"] = [x for x in ug if _norm_group(x) != g]

            await storage.async_save()
            conn.send_result(msg["id"], True)
        except Exception as e:
            conn.send_error(msg["id"], "delete_group_failed", str(e))

    websocket_api.async_register_command(hass, ws_get_state)
    websocket_api.async_register_command(hass, ws_add_user)
    websocket_api.async_register_command(hass, ws_update_user)
    websocket_api.async_register_command(hass, ws_delete_user)
    websocket_api.async_register_command(hass, ws_set_config)
    websocket_api.async_register_command(hass, ws_get_groups)
    websocket_api.async_register_command(hass, ws_add_group)
    websocket_api.async_register_command(hass, ws_delete_group)
