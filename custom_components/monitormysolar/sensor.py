from datetime import datetime, timedelta
import json
from typing import cast
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_MODE,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.event import (
    async_track_state_change_event,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from .const import DOMAIN, ENTITIES, FIRMWARE_CODES, LOGGER
from .coordinator import MonitorMySolarEntry
from .entity import MonitorMySolarEntity

async def async_setup_entry(hass, entry: MonitorMySolarEntry, async_add_entities):
    coordinator = entry.runtime_data
    inverter_brand = coordinator.inverter_brand
    firmware_code = coordinator.firmware_code

    brand_entities = ENTITIES.get(inverter_brand, {})
    sensors_config = brand_entities.get("sensor", {})

    entities = []

    # Loop through the sensors in the configuration
    for bank_name, sensors in sensors_config.items():
        for sensor in sensors:
            allowed_firmware_codes = sensor.get("allowed_firmware_codes", [])
            if not allowed_firmware_codes or firmware_code in allowed_firmware_codes:
                try:
                    # Check if the sensor is of type 'status' to create the StatusSensor class
                    if bank_name == "status":
                        entities.append(
                            StatusSensor(sensor, hass, entry, bank_name),
                        )
                    elif bank_name == "powerflow":
                        entities.append(
                            PowerFlowSensor(sensor, hass, entry, bank_name)
                        )
                    elif bank_name == "timestamp":
                        entities.append(
                            BankUpdateSensor(sensor, hass, entry, bank_name)
                        )
                    elif bank_name == "warning":
                        entities.append(
                            FaultWarningSensor(sensor, hass, entry, bank_name)
                        )
                    elif bank_name == "fault":
                        entities.append(
                            FaultWarningSensor(sensor, hass, entry, bank_name)
                        )
                    elif bank_name == "calculated":
                        entities.append(
                            CalculatedSensor(sensor, hass, entry, bank_name)
                        )
                    elif bank_name == "temperature":
                        entities.append(
                            TemperatureSensor(sensor, hass, entry, bank_name)
                        )
                    else:
                        entities.append(
                            InverterSensor(sensor, hass, entry, bank_name)
                        )
                except Exception as e:
                    LOGGER.error(f"Error setting up sensor {sensor}: {e}")

    async_add_entities(entities)


class InverterSensor(MonitorMySolarEntity, SensorEntity):
    def __init__(self, sensor_info, hass, entry, bank_name):
        """Initialize the sensor."""
        LOGGER.debug(f"Initializing sensor with info: {sensor_info}")
        self.coordinator = entry.runtime_data
        self.sensor_info = sensor_info
        self._name = sensor_info["name"]
        self._unique_id = f"{entry.entry_id}_{sensor_info['unique_id']}".lower()
        self._state = None
        self._dongle_id = self.coordinator.dongle_id
        self._device_id = self.coordinator.dongle_id
        self._sensor_type = sensor_info["unique_id"]
        self._bank_name = bank_name
        self.entity_id: str = f"sensor.{self._device_id}_{self._sensor_type.lower()}"
        self.hass = hass
        self._manufacturer = entry.data.get("inverter_brand")
        LOGGER.debug(f"Initialized sensor {self.entity_id}")

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
    def state_class(self):
        return self.sensor_info.get("state_class")

    @property
    def unit_of_measurement(self):
        return self.sensor_info.get("unit_of_measurement")

    @property
    def device_class(self):
        return self.sensor_info.get("device_class")

    @property
    def last_reset(self):
        """Return the time when the sensor was last reset (midnight)."""
        if self.state_class == "total":
            return datetime.min
        return None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._dongle_id)},
            "name": f"Inverter {self._dongle_id}",
            "manufacturer": f"{self._manufacturer}",
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""

        # This method is called by your DataUpdateCoordinator when a successful update runs.
        if self.entity_id in self.coordinator.entities:
            value = self.coordinator.entities[self.entity_id]
            if value is not None:
                if self._sensor_type == "RunningTime" and isinstance(value, (float, int)):
                    # Convert seconds to HH:MM:SS format
                    seconds = int(value)
                    hours, remainder = divmod(seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    self._state = f"{hours:02}:{minutes:02}:{seconds:02}"
                else:
                    self._state = (
                        round(value, 2) if isinstance(value, (float, int)) else value
                    )
                self.async_write_ha_state()
        else:
            LOGGER.warning(f"entity {self.entity_id} key not found")
        


class StatusSensor(MonitorMySolarEntity, SensorEntity):
    def __init__(self, sensor_info, hass, entry, bank_name):
        """Initialize the sensor."""
        LOGGER.debug(f"Initializing sensor with info: {sensor_info}")
        self.coordinator = entry.runtime_data
        self.sensor_info = sensor_info
        self._name = sensor_info["name"]
        self._unique_id = f"{entry.entry_id}_{sensor_info['unique_id']}".lower()
        self._state = None
        self._dongle_id = self.coordinator.dongle_id
        self._device_id = self.coordinator.dongle_id
        self._sensor_type = sensor_info["unique_id"]
        self._bank_name = bank_name
        self.entity_id = f"sensor.{self._device_id}_{self._sensor_type.lower()}"
        self.hass = hass
        self._manufacturer = entry.data.get("inverter_brand")
        self._expected_attributes = sensor_info.get("attributes", [])

        # Initialize attributes with default values
        self._attributes = {attr: "unknown" for attr in self._expected_attributes}

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
    def state_class(self):
        return self.sensor_info.get("state_class")

    @property
    def unit_of_measurement(self):
        return self.sensor_info.get("unit")

    @property
    def device_class(self):
        return self.sensor_info.get("device_class")

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._dongle_id)},
            "name": f"Inverter {self._dongle_id}",
            "manufacturer": f"{self._manufacturer}",
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        if self.entity_id in self.coordinator.entities:
            value = self.coordinator.entities[self.entity_id]
            if isinstance(value, dict):
                # Extract the 'uptime' for the sensor's state
                self._state = value.get("uptime")
                LOGGER.debug(f'State updated to: {self._state}')

                # Update the sensor's attributes based on the expected attributes list
                for attr in self._expected_attributes:
                    self._attributes[attr] = value.get(attr, "unknown")

                LOGGER.debug(f'Attributes updated to: {self._attributes}')

                self.async_write_ha_state()

class PowerFlowSensor(MonitorMySolarEntity, SensorEntity):
    def __init__(self, sensor_info, hass, entry, bank_name):
        """Initialize the Power Flow sensor."""
        self.coordinator = entry.runtime_data
        self.sensor_info = sensor_info
        self._name = sensor_info["name"]
        self._unique_id = f"{entry.entry_id}_{sensor_info['unique_id']}".lower()
        self._state = None
        self._dongle_id = self.coordinator.dongle_id
        self._device_id = self.coordinator.dongle_id
        self._sensor_type = sensor_info["unique_id"]
        self.entity_id = f"sensor.{self._device_id}_{self._sensor_type.lower()}"
        self.hass = hass
        self._manufacturer = entry.data.get("inverter_brand")
        self._attribute1 = sensor_info.get("attribute1")
        self._attribute2 = sensor_info.get("attribute2")
        self._value1 = 0
        self._value2 = 0

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
    def state_class(self):
        return self.sensor_info.get("state_class")

    @property
    def unit_of_measurement(self):
        return self.sensor_info.get("unit_of_measurement")

    @property
    def device_class(self):
        return self.sensor_info.get("device_class")


    @property
    def extra_state_attributes(self):
        return {
            self._attribute1: self._value1,
            self._attribute2: self._value2,

        }

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._dongle_id)},
            "name": f"Inverter {self._dongle_id}",
            "manufacturer": f"{self._manufacturer}",
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        attr1_entity_id = f"sensor.{self.coordinator.dongle_id}_{self._attribute1.lower()}"
        attr2_entity_id = f"sensor.{self.coordinator.dongle_id}_{self._attribute2.lower()}"
        if attr1_entity_id in self.coordinator.entities:
            value = self.coordinator.entities[attr1_entity_id]
            if value is not None:
                self._value1 = float(value)
        if attr2_entity_id in self.coordinator.entities:
            value = self.coordinator.entities[attr2_entity_id]
            if value is not None:
                self._value1 = float(value)
                # if event_entity_id.endswith(self._attribute1.lower()):
                #     self._value1 = float(value)
                # elif event_entity_id.endswith(self._attribute2.lower()):
                #     self._value2 = float(value)

        # Calculate the flow value
        if self._value1 > 0:
            self._state = -1 * self._value1
        else:
            self._state = self._value2

        self.async_write_ha_state()

class CombinedSensor(MonitorMySolarEntity, SensorEntity):
    def __init__(self, sensor_info, hass, entry, dongle_id):
        """Initialize the Combined sensor."""
        self.coordinator = entry.runtime_data
        self.sensor_info = sensor_info
        self._name = sensor_info["name"]
        self._unique_id = f"{entry.entry_id}_{sensor_info['unique_id']}".lower()
        self._state = None
        self._dongle_id = self.coordinator.dongle_id
        self._device_id = self.coordinator.dongle_id
        self._sensor_type = sensor_info["unique_id"]
        self.entity_id = f"sensor.{self._device_id}_{self._sensor_type.lower()}"
        self.hass = hass
        self._manufacturer = entry.data.get("inverter_brand")
        self._attributes = sensor_info.get("attributes", [])
        self._sensor_values = {attr: 0.0 for attr in self._attributes}  # Store individual sensor values

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
    def state_class(self):
        return self.sensor_info.get("state_class")

    @property
    def unit_of_measurement(self):
        return self.sensor_info.get("unit_of_measurement")

    @property
    def device_class(self):
        return self.sensor_info.get("device_class")


    @property
    def extra_state_attributes(self):
        return self._sensor_values

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._dongle_id)},
            "name": f"Inverter {self._dongle_id}",
            "manufacturer": f"{self._manufacturer}",
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        LOGGER.warning(f"CombinedSensor id: {self.entity_id}")
        LOGGER.warning(f"sensor_values: {self._sensor_values}")
        if self.entity_id in self.coordinator.entities:
            value = self.coordinator.entities[self.entity_id]
            if value is not None:

                if self.entity_id in self._sensor_values:
                    self._sensor_values[self.entity_id] = float(value)

                    # Example operation: Summing all sensor values
                    self._state = sum(self._sensor_values.values())
                    self.async_write_ha_state()

class BankUpdateSensor(MonitorMySolarEntity, SensorEntity):
    def __init__(self, sensor_info, hass, entry, bank_name):
        """Initialize the Bank Update sensor."""
        self.coordinator = entry.runtime_data
        self.sensor_info = sensor_info
        self._name = sensor_info["name"]
        self._unique_id = f"{entry.entry_id}_{sensor_info['unique_id']}".lower()
        self._state = None
        self._dongle_id = self.coordinator.dongle_id
        self._device_id = self.coordinator.dongle_id
        self._sensor_type = sensor_info["unique_id"]
        self.entity_id = f"sensor.{self._device_id}_{self._sensor_type.lower()}"
        self.hass = hass
        self._manufacturer = entry.data.get("inverter_brand")

        # Initialize attributes with None values
        self._attributes = {attr: None for attr in sensor_info.get("attributes", [])}

        super().__init__(self.coordinator)

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def state(self):
        """Return the most recent update time."""
        return self._state

    @property
    def device_class(self):
        return self.sensor_info.get("device_class")

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._dongle_id)},
            "name": f"Inverter {self._dongle_id}",
            "manufacturer": f"{self._manufacturer}",
        }

    @callback
    def _handle_bank_update(self, event):
        """Handle bank update events."""
        bank_name = event.data.get("bank_name")
        LOGGER.debug(f"Update Event Called for: {bank_name}")
        if bank_name:
            current_time = datetime.now().isoformat()
            attr_name = f"{bank_name}_last_update"
            LOGGER.debug(f"Updating Attribute name: {attr_name}")

            if attr_name in self._attributes:
                self._attributes[attr_name] = current_time
                self._state = current_time  # Update state to most recent update
                self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Subscribe to events when added to hass."""
        LOGGER.debug(f"Subscribing to bank update event for {self.entity_id}")
        self.async_on_remove(
            self.hass.bus.async_listen(f"{DOMAIN}_bank_updated", self._handle_bank_update)
        )

class FaultWarningSensor(MonitorMySolarEntity, SensorEntity):
    def __init__(self, sensor_info, hass, entry, bank_name):
        """Initialize the fault/warning sensor."""
        self.coordinator = entry.runtime_data
        self.sensor_info = sensor_info
        self._name = sensor_info["name"]
        self._unique_id = f"{entry.entry_id}_{sensor_info['unique_id']}".lower()
        self._state = None
        self._dongle_id = self.coordinator.dongle_id
        self._device_id = self.coordinator.dongle_id
        self._sensor_type = sensor_info["unique_id"]
        self.entity_id = f"sensor.{self._device_id}_{self._sensor_type.lower()}"
        self.hass = hass
        self._manufacturer = entry.data.get("inverter_brand")
        self._bank_name = bank_name

        self._history = []
        self._state = "No Fault" if "fault" in sensor_info["unique_id"] else "No Warning"
        self._value = 0

        super().__init__(self.coordinator)

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._value == 0:
            return "No Fault" if "fault" in self._sensor_type else "No Warning"
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {
            "value": self._value,
            "history": self._history
        }
        return attrs
    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._dongle_id)},
            "name": f"Inverter {self._dongle_id}",
            "manufacturer": f"{self._manufacturer}",
        }
   

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        if self.entity_id in self.coordinator.entities:
            value_data = self.coordinator.entities[self.entity_id]
            LOGGER.debug(f"Value data: {value_data}")
            if isinstance(value_data, dict):
                self._value = value_data.get("value", 0)
                description = value_data.get("description")
                LOGGER.debug(f"Description: {description}")

                if description:  # New fault/warning
                    self._state = description
                    start_time = value_data.get("start_time", "Unknown")
                    end_time = value_data.get("end_time", "Ongoing")

                    # Check if the last entry in history is ongoing and matches the current description
                    if self._history and self._history[-1]["end_time"] == "Ongoing" and self._history[-1]["description"] == description:
                        # Update the end time of the ongoing event
                        self._history[-1]["end_time"] = end_time
                    else:
                        # Append a new entry for a new event
                        self._history.append({
                            "description": description,
                            "value": self._value,
                            "start_time": start_time,
                            "end_time": end_time
                        })
                    LOGGER.debug(f"History: {self._history}")
                else:  # Reset state
                    self._state = "No Fault" if "fault" in self._sensor_type else "No Warning"

                    # If there's an ongoing issue in history, mark it as resolved
                    if self._history and self._history[-1]["end_time"] == "Ongoing":
                        self._history[-1]["end_time"] = value_data.get("timestamp", "Unknown")

            self.async_write_ha_state()

class CalculatedSensor(MonitorMySolarEntity, SensorEntity):
    def __init__(self, sensor_info, hass, entry, bank_name):
        """Initialize the calculated sensor."""
        self.coordinator = entry.runtime_data
        self.sensor_info = sensor_info
        self._name = sensor_info["name"]
        self.entry = entry  # Store the entry for use in event handling
        self._unique_id = f"{entry.entry_id}_{sensor_info['unique_id']}".lower()
        self._state = None

        # Store the formatted IDs
        self._dongle_id = self.coordinator.dongle_id  # For device_info
        self._formatted_id = self.coordinator.dongle_id.replace(":", "_")   # For sensor entity matching

        self._sensor_type = sensor_info["unique_id"]
        self.entity_id = f"sensor.{self._formatted_id}_{self._sensor_type.lower()}"
        self.hass = hass
        self._manufacturer = entry.data.get("inverter_brand")
        self._bank_name = bank_name

        # Get calculation info
        self._calculation = sensor_info.get("calculation", {})
        self._operation = self._calculation.get("operation")
        self._source_sensors = self._calculation.get("sensors", [])
        self._sensor_values = {sensor: 0 for sensor in self._source_sensors}

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
    def state_class(self):
        return self.sensor_info.get("state_class")

    @property
    def unit_of_measurement(self):
        return self.sensor_info.get("unit_of_measurement")

    @property
    def device_class(self):
        return self.sensor_info.get("device_class")

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._dongle_id)},
            "name": f"Inverter {self._dongle_id}",
            "manufacturer": f"{self._manufacturer}",
        }

    def _calculate_state(self):
        """Calculate the state based on the operation and sensor values."""
        if self._operation == "division":
            numerator = self._sensor_values[self._source_sensors[0]]
            denominator = self._sensor_values[self._source_sensors[1]]
            if denominator and denominator != 0:
                self._state = round(numerator / denominator, 2)
            else:
                self._state = 0

        elif self._operation == "battery_time":
            capacity_ah = self._sensor_values.get("batcapacity", 0)
            voltage = self._sensor_values.get("vbat", 0)
            load_watts = self._sensor_values.get("pload", 0)
            battery_flow = self._sensor_values.get("batteryflow_live", 0)
            soc = self._sensor_values.get("soc", 0)
            pv_power = self._sensor_values.get("pall", 0)

            if capacity_ah > 0 and voltage > 0 and soc > 0:
                usable_energy_wh = (capacity_ah * voltage) * (soc / 100)
                net_load = max(load_watts - pv_power, 0)
                adjusted_load = net_load - battery_flow

                if adjusted_load > 0:
                    self._state = round(usable_energy_wh / adjusted_load, 2)
                else:
                    self._state = "Charging"

                # Calculate attributes
                self._attr_extra_state_attributes = {
                    "calculated_kwh_storage_total": round(capacity_ah * voltage / 1000, 2),
                    "calculated_kwh_left": round((capacity_ah * voltage * (soc / 100)) / 1000, 2),
                }

                # Calculate time battery empty
                if adjusted_load > 0:
                    hours_remaining = usable_energy_wh / adjusted_load
                    current_time = datetime.now()
                    empty_time = current_time + timedelta(hours=hours_remaining)

                    self._attr_extra_state_attributes.update({
                        "time_battery_empty": empty_time.strftime('%Y-%m-%d %H:%M:%S'),
                        "human_readable_time_left": f"{int(hours_remaining)} hours, {int((hours_remaining - int(hours_remaining)) * 60)} minutes"
                    })
            else:
                self._state = "Unavailable"
                self._attr_extra_state_attributes = {
                    "calculated_kwh_storage_total": "Unavailable",
                    "calculated_kwh_left": "Unavailable",
                    "time_battery_empty": "Unavailable",
                    "human_readable_time_left": "Unavailable"
                }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        # Get our source sensor IDs using the entry ID format
        source_entity_ids = {
            f"sensor.{self._formatted_id}_{sensor.lower()}": sensor
            for sensor in self._source_sensors
        }
        for entity_id in source_entity_ids.keys():
            # Check if this event matches one of our source sensors
             if entity_id in self.coordinator.entities:
                value = self.coordinator.entities[entity_id]
                if value is not None:
                    sensor_name = source_entity_ids[entity_id]
                    self._sensor_values[sensor_name] = float(value)

                    # LOGGER.warning(
                    #     f"Updated {sensor_name} value to {value} for calculated sensor {self.entity_id}"
                    # )

                    self._calculate_state()
                    self.async_write_ha_state()

class TemperatureSensor(MonitorMySolarEntity, SensorEntity):
    def __init__(self, sensor_info, hass, entry, bank_name):
        """Initialize the temperature sensor."""
        LOGGER.debug(f"Initializing sensor with info: {sensor_info}")
        self.coordinator = entry.runtime_data
        self.sensor_info = sensor_info
        self._name = sensor_info["name"]
        self._unique_id = f"{entry.entry_id}_{sensor_info['unique_id']}".lower()
        self._state = None
        self._dongle_id = self.coordinator.dongle_id
        self._device_id = self.coordinator.dongle_id
        self._sensor_type = sensor_info["unique_id"]
        self._bank_name = bank_name
        self.entity_id = f"sensor.{self._device_id}_{self._sensor_type.lower()}"
        self.hass = hass
        self._manufacturer = entry.data.get("inverter_brand")

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
    def state_class(self):
        return self.sensor_info.get("state_class")

    @property
    def unit_of_measurement(self):
        if self.hass.config.units is US_CUSTOMARY_SYSTEM:
            return UnitOfTemperature.FAHRENHEIT
        else:
            return UnitOfTemperature.CELSIUS

    @property
    def device_class(self):
        return self.sensor_info.get("device_class")

    @property
    def last_reset(self):
        """Return the time when the sensor was last reset (midnight)."""
        if self.state_class == "total":
            return datetime.min
        return None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._dongle_id)},
            "name": f"Inverter {self._dongle_id}",
            "manufacturer": f"{self._manufacturer}",
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        if self.entity_id in self.coordinator.entities:
            value = self.coordinator.entities[self.entity_id]
            if value is not None:
                # Default state to value sent in.
                self._state = (
                    round(value, 2) if isinstance(value, (float, int)) else value
                )
                # Check for HA config values and convert if neccessary.
                if self.hass.config.units is US_CUSTOMARY_SYSTEM:
                    # Const defines Celsius but HA should show Fahrenheit.
                    if UnitOfTemperature.FAHRENHEIT != self.sensor_info.get("unit_of_measurement"):
                        self._state = (
                            round( (((value)*9/5)+32), 2 ) if isinstance(value, (float, int)) else value
                        )
                else:
                    # Const defines Fahrenheit but HA should show Celsius.
                    if UnitOfTemperature.CELSIUS != self.sensor_info.get("unit_of_measurement"):
                        self._state = (
                            round( ((value)-32/(9/5)), 2 ) if isinstance(value, (float, int)) else value
                        )
                LOGGER.debug(f"Sensor {self.entity_id} state updated to {self._state}")
                self.async_write_ha_state()
