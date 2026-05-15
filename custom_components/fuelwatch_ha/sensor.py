from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    CONF_FUEL_TYPE,
    CONF_NAME,
    CONF_PINNED_STATIONS,
    CONF_RADIUS,
    DOMAIN,
)
from .coordinator import FuelWatchCoordinator

TODAY_SENSOR_TYPES = ["cheapest", "average", "most_expensive"]
TOMORROW_SENSOR_TYPES = ["tomorrow_cheapest", "tomorrow_average", "tomorrow_most_expensive"]


async def async_setup_entry(hass, entry, async_add_entities):
    config = dict(entry.data)

    coordinator = FuelWatchCoordinator(hass, config, entry.title)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    pinned = config.get(CONF_PINNED_STATIONS, [])
    if pinned:
        sensors = [
            FuelWatchStationSensor(coordinator, entry, name, is_tomorrow)
            for name in pinned
            for is_tomorrow in (False, True)
        ]
    else:
        sensors = [
            FuelWatchSensor(coordinator, entry, sensor_type)
            for sensor_type in TODAY_SENSOR_TYPES + TOMORROW_SENSOR_TYPES
        ]

    async_add_entities(sensors)


def _device_name(config, entry_title):
    location = config.get(CONF_NAME, entry_title)
    fuel = config.get(CONF_FUEL_TYPE, "")
    return f"{location} - {fuel}"


class FuelWatchSensor(CoordinatorEntity, SensorEntity):
    has_entity_name = True

    def __init__(self, coordinator, entry, sensor_type):
        super().__init__(coordinator)
        self._config = dict(entry.data)
        self._entry_title = entry.title
        self._entry_id = entry.entry_id
        self._type = sensor_type
        self._is_tomorrow = sensor_type.startswith("tomorrow_")
        self._base_type = sensor_type.removeprefix("tomorrow_")
        self._is_legacy_entry = CONF_NAME not in self._config
        self._slug = slugify(self._config.get(CONF_NAME, self._entry_title))

    @property
    def name(self):
        base_label = self._base_type.replace("_", " ").title()
        qualifier = " Tomorrow" if self._is_tomorrow else ""
        return f"{base_label}{qualifier}"

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=_device_name(self._config, self._entry_title),
        )

    @property
    def icon(self):
        return "mdi:gas-station"

    @property
    def suggested_object_id(self):
        return f"{self._base_type}{'_tomorrow' if self._is_tomorrow else ''}"

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


class FuelWatchStationSensor(CoordinatorEntity, SensorEntity):
    has_entity_name = True

    def __init__(self, coordinator, entry, station_name, is_tomorrow):
        super().__init__(coordinator)
        self._config = dict(entry.data)
        self._entry_title = entry.title
        self._entry_id = entry.entry_id
        self._station_name = station_name
        self._is_tomorrow = is_tomorrow
        self._location_slug = slugify(self._config.get(CONF_NAME, entry.title))
        self._station_slug = slugify(station_name)

    @property
    def name(self):
        qualifier = " Tomorrow" if self._is_tomorrow else ""
        return f"{self._station_name}{qualifier}"

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=_device_name(self._config, self._entry_title),
        )

    @property
    def icon(self):
        return "mdi:gas-station"

    @property
    def suggested_object_id(self):
        return f"{self._station_slug}{'_tomorrow' if self._is_tomorrow else ''}"

    @property
    def available(self):
        data = self.coordinator.data
        if data is None:
            return False
        source = data.get("tomorrow") if self._is_tomorrow else data
        if source is None:
            return False
        return source.get("stations", {}).get(self._station_name) is not None

    @property
    def state(self):
        data = self.coordinator.data
        if not data:
            return None
        source = data.get("tomorrow") if self._is_tomorrow else data
        if not source:
            return None
        station = source.get("stations", {}).get(self._station_name)
        if station is None:
            return None
        return station["price"]

    @property
    def native_unit_of_measurement(self):
        return "c/L"

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        if not data:
            return {}
        source = data.get("tomorrow") if self._is_tomorrow else data
        if not source:
            return {}
        station = source.get("stations", {}).get(self._station_name)
        if station is None:
            return {}

        return {
            "location_name": data.get("location_label"),
            "radius_km": self._config.get(CONF_RADIUS),
            "fuel_type": self._config.get(CONF_FUEL_TYPE),
            "station": station.get("trading_name"),
            "address": station.get("address"),
            "suburb": station.get("location"),
            "distance_km": station.get("distance"),
            "last_updated": station.get("date"),
        }

    @property
    def unique_id(self):
        fuel = self._config.get(CONF_FUEL_TYPE, "")
        radius = self._config.get(CONF_RADIUS, "")
        prefix = "tomorrow_" if self._is_tomorrow else ""
        return f"fuelwatch_{prefix}station_{self._station_slug}_{self._location_slug}_{fuel}_{radius}"
