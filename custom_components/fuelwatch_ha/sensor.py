from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    CONF_FUEL_TYPE,
    CONF_NAME,
    CONF_RADIUS,
)
from .coordinator import FuelWatchCoordinator

TODAY_SENSOR_TYPES = ["cheapest", "average", "most_expensive"]
TOMORROW_SENSOR_TYPES = ["tomorrow_cheapest", "tomorrow_average", "tomorrow_most_expensive"]


async def async_setup_entry(hass, entry, async_add_entities):
    config = dict(entry.data)

    coordinator = FuelWatchCoordinator(hass, config, entry.title)
    await coordinator.async_config_entry_first_refresh()

    sensors = [
        FuelWatchSensor(coordinator, entry, sensor_type)
        for sensor_type in TODAY_SENSOR_TYPES + TOMORROW_SENSOR_TYPES
    ]

    async_add_entities(sensors)


class FuelWatchSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, sensor_type):
        super().__init__(coordinator)
        self._config = dict(entry.data)
        self._entry_title = entry.title
        self._type = sensor_type
        self._is_tomorrow = sensor_type.startswith("tomorrow_")
        self._base_type = sensor_type.removeprefix("tomorrow_")
        self._is_legacy_entry = CONF_NAME not in self._config
        self._name_suffix = self._config.get(CONF_NAME, self._entry_title)
        self._slug = slugify(self._name_suffix)

    @property
    def name(self):
        base_label = self._base_type.replace("_", " ").title()
        qualifier = " Tomorrow" if self._is_tomorrow else ""

        if self._is_legacy_entry:
            return f"{base_label} Fuel{qualifier}"

        return f"{base_label} Fuel{qualifier} {self._name_suffix}"

    @property
    def icon(self):
        return "mdi:gas-station"

    @property
    def suggested_object_id(self):
        if self._is_tomorrow:
            return f"tomorrow_{self._base_type}_fuel_{self._slug}"
        return f"{self._type}_fuel_{self._slug}"

    @property
    def available(self):
        if not self._is_tomorrow:
            return super().available
        return (
            self.coordinator.data is not None
            and self.coordinator.data.get("tomorrow") is not None
        )

    @property
    def state(self):
        data = self.coordinator.data
        if not data:
            return None

        source = data["tomorrow"] if self._is_tomorrow else data
        if source is None:
            return None

        if self._base_type == "average":
            return source["average"]

        return source[self._base_type]["price"]

    @property
    def native_unit_of_measurement(self):
        return "c/L"

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        if not data:
            return {}

        source = data["tomorrow"] if self._is_tomorrow else data
        if source is None:
            return {}

        base_attributes = {
            "location_name": data.get("location_label"),
            "radius_km": self._config.get(CONF_RADIUS),
            "fuel_type": self._config.get(CONF_FUEL_TYPE),
        }

        if self._base_type == "average":
            return {
                **base_attributes,
                "stations_count": source["count"],
            }

        fuel = source[self._base_type]

        return {
            **base_attributes,
            "station": fuel.get("trading_name"),
            "address": fuel.get("address"),
            "suburb": fuel.get("location"),
            "distance_km": fuel.get("distance"),
            "last_updated": fuel.get("date"),
        }

    @property
    def unique_id(self):
        if self._is_legacy_entry:
            return (
                f"fuelwatch_{self._type}_"
                f"{self._config.get(CONF_FUEL_TYPE)}_{self._config.get(CONF_RADIUS)}"
            )

        return (
            f"fuelwatch_{self._type}_{self._slug}_"
            f"{self._config.get(CONF_FUEL_TYPE)}_{self._config.get(CONF_RADIUS)}"
        )
