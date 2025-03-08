from datetime import datetime, timedelta
import asyncio
from homeassistant.components.time import TimeEntity
from homeassistant.core import callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
)
from homeassistant.const import (
    STATE_UNKNOWN,
)
from .const import DOMAIN, ENTITIES, LOGGER
from .coordinator import MonitorMySolarEntry
from .entity import MonitorMySolarEntity

async def async_setup_entry(hass, entry: MonitorMySolarEntry, async_add_entities):
    coordinator = entry.runtime_data
    inverter_brand = coordinator.inverter_brand
    brand_entities = ENTITIES.get(inverter_brand, {})

    entities = []

    # Setup Time entities
    time_config = brand_entities.get("time", {})
    for bank_name, time_entities in time_config.items():
        for time_entity in time_entities:
            entities.append(InverterTime(time_entity, hass, entry))

    async_add_entities(entities, True)

class InverterTime(MonitorMySolarEntity, TimeEntity):
    def __init__(self, entity_info, hass, entry: MonitorMySolarEntry):
        """Initialize the Time entity."""
        LOGGER.debug(f"Initializing Time entity with info: {entity_info}")
        self.coordinator = entry.runtime_data
        self.entity_info = entity_info
        self._name = entity_info["name"]
        self._unique_id = f"{entry.entry_id}_{entity_info['unique_id']}".lower()
        self._state = None
        self._dongle_id = self.coordinator.dongle_id
        self._device_id = self.coordinator.dongle_id
        self._entity_type = entity_info["unique_id"]
        self.entity_id = f"time.{self._device_id}_{self._entity_type.lower()}"
        self.hass = hass
        self._manufacturer = entry.data.get("inverter_brand")
        self._last_mqtt_update = None
        self._debounce_task = None

        super().__init__(self.coordinator)

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def state(self):
        return self._state

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._dongle_id)},
            "name": f"Inverter {self._dongle_id}",
            "manufacturer": f"{self._manufacturer}",
        }

    async def async_set_value(self, value):
        """Handle user input and send to MQTT."""
        now = datetime.now()

        # Check if the state has changed
        if self._state == value or self._state is None:
            LOGGER.debug(f"No change in state for {self.entity_id}. Skipping MQTT update.")
            return

        # Debounce logic to delay the MQTT update and prevent multiple messages
        if self._debounce_task:
            self._debounce_task.cancel()

        async def debounce():
            await asyncio.sleep(1)
            if self._last_mqtt_update and (now - self._last_mqtt_update).total_seconds() < 1:
                LOGGER.debug(f"Skipping MQTT update for {self.entity_id} due to rate limiting")
                return

            LOGGER.info(f"Setting time value for {self.entity_id} to {value}")
            self.update_state(value)
            await self.coordinator.mqtt_handler.send_update(
                self._dongle_id.replace("_", "-"),
                self.entity_info["unique_id"],
                value.isoformat(),
                self,
            )

        self._debounce_task = asyncio.create_task(debounce())

    @callback
    def update_state(self, value):
        """Update the state without triggering MQTT (e.g., from MQTT message)."""
        if self._state != value:
            self._state = value
            self._last_mqtt_update = datetime.now()
            LOGGER.debug(f"Time {self.entity_id} state updated to {value}")
            # Schedule state update on the main thread
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)

    def revert_state(self):
        """Revert to the previous state."""
        # Schedule state revert on the main thread
        self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""

        # This method is called by your DataUpdateCoordinator when a successful update runs.
        if self.entity_id in self.coordinator.entities:
            value = self.coordinator.entities[self.entity_id]
            if value is not None:
                self.update_state(value)
                self.async_write_ha_state()
