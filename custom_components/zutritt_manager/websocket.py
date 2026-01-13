from __future__ import annotations

import hashlib
import secrets

from homeassistant.components import websocket_api
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, SIGNAL_GROUPS_UPDATED


def _split_csv(s: str) -> list[str]:
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


def _norm_group(g: str) -> str:
    # canonical group id (entity_id safe)
    g = (g or "").strip()
    g = " ".join(g.split())
    g = g.replace(",", "")
    g = g.lower()
    # make entity_id safe
    g = g.replace(" ", "_")
    g = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in g)
    while "__" in g:
        g = g.replace("__", "_")
    return g.strip("_")


def _hash_pin(salt: str, pin: str) -> str:
    return hashlib.sha256((salt + pin).encode("utf-8")).hexdigest()


def _get_storage(hass):
    return hass.data.get(DOMAIN, {}).get("storage")



def _remove_group_entity_from_registry(hass, group_id: str) -> None:
    """Remove the group switch entity from HA's entity registry to avoid orphan warnings."""
    try:
        reg = er.async_get(hass)
        target_unique_id = f"{DOMAIN}_group_{group_id}"
        for ent_id, entry in list(reg.entities.items()):
            if entry.platform != "switch":
                continue
            if entry.domain != "switch":
                continue
            if entry.unique_id == target_unique_id:
                reg.async_remove(ent_id)
    except Exception:
        # never fail WS handler because of registry cleanup
        return

def _ensure_base_state(st: dict) -> dict:
    st.setdefault("users", [])
    st.setdefault("sources", {})
    st.setdefault("group_booleans", {})
    st.setdefault("groups", [])       # zentrale Gruppenliste
    st.setdefault("access_log", [])   # ✅ Log der letzten 30 Tage (wenn vorhanden)
    return st


def _sync_groups_from_users(st: dict) -> None:
    groups = st.setdefault("groups", [])
    known = set(_norm_group(x) for x in groups)
    for u in st.get("users", []):
        for g in u.get("groups", []) or []:
            gg = _norm_group(g)
            if gg and gg not in known:
                known.add(gg)
                groups.append(gg)
    groups[:] = sorted(set(_norm_group(x) for x in groups if _norm_group(x)))


def async_register_ws(hass):

    @websocket_api.websocket_command({"type": "zutritt_manager/get_state"})
    @websocket_api.async_response
    async def ws_get_state(hass, conn, msg):
        try:
            storage = _get_storage(hass)
            if not storage:
                conn.send_result(
                    msg["id"],
                    {
                        "users": [],
                        "groups": [],
                        "access_log": [],
                    },
                )
                return

            st = _ensure_base_state(storage.state)
            _sync_groups_from_users(st)

            # access_log kann groß sein -> trotzdem ok, aber wir begrenzen sicherheitshalber
            # (UI macht eh Filter). Wenn du mehr willst: Zahl erhöhen.
            access_log = st.get("access_log") or []
            if isinstance(access_log, list) and len(access_log) > 2000:
                access_log = access_log[-2000:]

            conn.send_result(
                msg["id"],
                {
                    "users": st.get("users", []),
                    "sources": st.get("sources", {}),
                    "group_booleans": st.get("group_booleans", {}),
                    "groups": st.get("groups", []),
                    "access_log": access_log,
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
            _remove_group_entity_from_registry(hass, g)
            async_dispatcher_send(hass, SIGNAL_GROUPS_UPDATED)
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

            groups_raw = _split_csv(msg.get("groups_csv", ""))
            groups = []
            seen = set()
            for x in groups_raw:
                gg = _norm_group(x)
                if gg and gg not in seen:
                    seen.add(gg)
                    groups.append(gg)
            u["groups"] = groups

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

            _sync_groups_from_users(st)

            await storage.async_save()
            _remove_group_entity_from_registry(hass, g)
            async_dispatcher_send(hass, SIGNAL_GROUPS_UPDATED)
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
            _remove_group_entity_from_registry(hass, g)
            async_dispatcher_send(hass, SIGNAL_GROUPS_UPDATED)
            conn.send_result(msg["id"], True)
        except Exception as e:
            conn.send_error(msg["id"], "delete_user_failed", str(e))

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
            normed = set(_norm_group(x) for x in groups)
            if g not in normed:
                groups.append(g)
            groups[:] = sorted(set(_norm_group(x) for x in groups if _norm_group(x)))

            await storage.async_save()
            _remove_group_entity_from_registry(hass, g)
            async_dispatcher_send(hass, SIGNAL_GROUPS_UPDATED)
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

            st["groups"] = [x for x in st.get("groups", []) if _norm_group(x) != g]

            for u in st.get("users", []):
                u["groups"] = [x for x in (u.get("groups") or []) if _norm_group(x) != g]

            await storage.async_save()
            _remove_group_entity_from_registry(hass, g)
            async_dispatcher_send(hass, SIGNAL_GROUPS_UPDATED)
            conn.send_result(msg["id"], True)
        except Exception as e:
            conn.send_error(msg["id"], "delete_group_failed", str(e))

    websocket_api.async_register_command(hass, ws_get_state)
    websocket_api.async_register_command(hass, ws_add_user)
    websocket_api.async_register_command(hass, ws_update_user)
    websocket_api.async_register_command(hass, ws_delete_user)
    websocket_api.async_register_command(hass, ws_add_group)
    websocket_api.async_register_command(hass, ws_delete_group)
