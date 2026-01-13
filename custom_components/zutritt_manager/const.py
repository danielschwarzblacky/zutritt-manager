DOMAIN = "zutritt_manager"

STORE_KEY = "zutritt_manager"
STORE_VERSION = 1

PANEL_URL = "zutritt"
PANEL_TITLE = "Zutritt"
PANEL_ICON = "mdi:shield-key"

DEFAULT_STATE = {
    "sources": {
        "halle_1": {
            "door_entity": "",
            "granted_boolean": "",
            "denied_boolean": "",
            "bell_boolean": "",
            "door_pulse_s": 3
        }
    },
    "group_booleans": {
        "chef": "",
        "lieferant": "",
        "mitarbeiter": ""
    },
    "users": []
}

# Dispatcher signal: groups list changed -> switch entities reload
SIGNAL_GROUPS_UPDATED = "zutritt_manager_groups_updated"

# default pulse length for group switches
IMPULSE_SECONDS = 1
