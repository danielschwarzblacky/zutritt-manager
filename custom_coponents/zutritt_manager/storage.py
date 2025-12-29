from homeassistant.helpers.storage import Store
from .const import STORE_KEY, STORE_VERSION, DEFAULT_STATE

class ZutrittStorage:
    def __init__(self, hass):
        self.store = Store(hass, STORE_VERSION, STORE_KEY)
        self.state = {}

    async def async_load(self):
        data = await self.store.async_load() or {}
        self.state = DEFAULT_STATE | data
        self.state.setdefault("users", [])
        return self.state

    async def async_save(self):
        await self.store.async_save(self.state)

    def get_state(self):
        return self.state
