DOMAIN = "zutritt_manager"

STORE_KEY = "zutritt_manager"
STORE_VERSION = 1

PANEL_URL = "zutritt"
PANEL_TITLE = "Zutritt"
PANEL_ICON = "mdi:shield-key"

EVENT_ZUTRITT = "esphome.zutritt_input"
EVENT_BELL = "esphome.halle_taster"
EVENT_ACCESS = "zutritt_manager.access"

DEFAULT_STATE = {
    "sources": {
        "halle_1": {
            "door_entity": "",
            "granted_boolean": "input_boolean.halle_keypad_granted",
            "denied_boolean": "input_boolean.halle_keypad_denied",
            "bell_boolean": "input_boolean.halle_klingel",
            "door_pulse_s": 3
        }
    },
    "group_booleans": {
        "chef": "input_boolean.zutritt_group_chef",
        "lieferant": "input_boolean.zutritt_group_lieferant",
        "mitarbeiter": "input_boolean.zutritt_group_mitarbeiter"
    },
    "users": []
}
