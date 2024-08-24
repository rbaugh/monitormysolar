import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.core import callback
from .const import DOMAIN, ENTITIES, FIRMWARE_CODES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    inverter_brand = entry.data.get("inverter_brand")
    dongle_id = entry.data.get("dongle_id").lower().replace("-", "_")
    firmware_code = entry.data.get("firmware_code")
    device_type = FIRMWARE_CODES.get(firmware_code, {}).get("Device_Type", "")

    brand_entities = ENTITIES.get(inverter_brand, {})
    buttons_config = brand_entities.get("button", {})

    entities = []
    for bank_name, buttons in buttons_config.items():
        for button in buttons:
            try:
                entities.append(
                    FirmwareUpdateButton(button, hass, entry, dongle_id, bank_name)
                )
            except Exception as e:
                _LOGGER.error(f"Error setting up button {button}: {e}")

    async_add_entities(entities, True)
class FirmwareUpdateButton(ButtonEntity):
    def __init__(self, button_info, hass, entry, dongle_id, bank_name):
        """Initialize the button."""
        _LOGGER.debug(f"Initializing button with info: {button_info}, "
                      f"hass: {hass}, entry: {entry}, dongle_id: {dongle_id}, bank_name: {bank_name}")
        self.button_info = button_info
        self._name = button_info["name"]
        self._unique_id = f"{entry.entry_id}_{button_info['unique_id']}".lower()
        self._dongle_id = dongle_id.lower().replace("-", "_")
        self._device_id = dongle_id.lower().replace("-", "_")
        self._button_type = button_info["unique_id"]
        self._bank_name = bank_name
        self.entity_id = f"button.{self._device_id}_{self._button_type.lower()}"
        self.hass = hass
        self._manufacturer = entry.data.get("inverter_brand")

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._dongle_id)},
            "name": f"Inverter {self._dongle_id}",
            "manufacturer": f"{self._manufacturer}",
        }

    async def async_press(self):
        """Handle the button press."""
        # Ensure dongle_id is formatted correctly with underscores
        formatted_dongle_id = self._dongle_id.replace(":", "_")

        sw_version_entity_id = f"sensor.{formatted_dongle_id}_sw_version"
        latest_firmware_entity_id = f"sensor.{formatted_dongle_id}_latestfirmwareversion"

        _LOGGER.warning(f"Software Version Entity ID: {sw_version_entity_id}")
        _LOGGER.warning(f"Latest Firmware Version Entity ID: {latest_firmware_entity_id}")

        sw_version = self.hass.states.get(sw_version_entity_id)
        latest_firmware_version = self.hass.states.get(latest_firmware_entity_id)

        if sw_version is None or latest_firmware_version is None:
            _LOGGER.error(f"Could not retrieve version information for {formatted_dongle_id}.")
            return

        sw_version = sw_version.state
        latest_firmware_version = latest_firmware_version.state

        if sw_version < latest_firmware_version:
            # Firmware update is needed
            _LOGGER.info(f"Firmware update button pressed for {formatted_dongle_id}")
            topic = f"{self._dongle_id}/update"
            payload = "updatedongle"
            self.hass.components.mqtt.async_publish(self.hass, topic, payload)
            _LOGGER.info(f"Firmware update request sent to {topic} with payload {payload}")
        else:
            # No update needed
            _LOGGER.info(f"No firmware update needed for {formatted_dongle_id}. SW_VERSION: {sw_version}, LatestFirmwareVersion: {latest_firmware_version}")
            self.hass.bus.async_fire(f"{DOMAIN}_notification", {
                "title": "Firmware Update",
                "message": "No update available for the dongle."
            })
