import logging

import voluptuous as vol
from fuelwatcher import FuelWatch
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_FUEL_TYPE,
    CONF_LATITUDE,
    CONF_LOCATION_MODE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_PINNED_STATIONS,
    CONF_RADIUS,
    CONF_ZONE_NAME,
    DEFAULT_NAME,
    DEFAULT_RADIUS,
    DEFAULT_ZONE_NAME,
    DOMAIN,
    FUEL_TYPE_TO_PRODUCT,
    LOCATION_MODE_COORDINATES,
    LOCATION_MODE_HOME,
    LOCATION_MODE_ZONE,
)
from .coordinator import haversine

_LOGGER = logging.getLogger(__name__)

FUEL_TYPES = [
    "ULP",
    "Diesel",
    "Brand Diesel",
    "PULP",
    "LPG",
    "98RON",
    "E85",
]

LOCATION_MODE_LABELS = {
    LOCATION_MODE_HOME: "Home Location",
    LOCATION_MODE_ZONE: "Home Assistant Zone",
    LOCATION_MODE_COORDINATES: "Coordinates",
}


class FuelWatchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._step_one_input = {}

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            data, errors = self._validate_step_one(user_input)
            if not errors:
                self._step_one_input = data

                if data[CONF_LOCATION_MODE] == LOCATION_MODE_HOME:
                    return await self.async_step_station()

                if data[CONF_LOCATION_MODE] == LOCATION_MODE_ZONE:
                    return await self.async_step_zone()

                return await self.async_step_coordinates()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_FUEL_TYPE): vol.In(FUEL_TYPES),
                    vol.Required(CONF_RADIUS, default=DEFAULT_RADIUS): int,
                    vol.Required(
                        CONF_LOCATION_MODE, default=LOCATION_MODE_HOME
                    ): vol.In(LOCATION_MODE_LABELS),
                }
            ),
            errors=errors,
        )

    async def async_step_zone(self, user_input=None):
        errors = {}

        if user_input is not None:
            zone_name = user_input.get(CONF_ZONE_NAME, "").strip()
            if not zone_name:
                errors[CONF_ZONE_NAME] = "zone_required"
            else:
                self._step_one_input = {
                    **self._step_one_input,
                    CONF_ZONE_NAME: zone_name,
                    CONF_LATITUDE: None,
                    CONF_LONGITUDE: None,
                }
                return await self.async_step_station()

        return self.async_show_form(
            step_id="zone",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ZONE_NAME, default=DEFAULT_ZONE_NAME): str,
                }
            ),
            errors=errors,
        )

    async def async_step_coordinates(self, user_input=None):
        errors = {}

        if user_input is not None:
            latitude = self._parse_coordinate(
                user_input.get(CONF_LATITUDE, ""), CONF_LATITUDE, -90, 90, errors
            )
            longitude = self._parse_coordinate(
                user_input.get(CONF_LONGITUDE, ""), CONF_LONGITUDE, -180, 180, errors
            )

            if not errors:
                self._step_one_input = {
                    **self._step_one_input,
                    CONF_ZONE_NAME: DEFAULT_ZONE_NAME,
                    CONF_LATITUDE: latitude,
                    CONF_LONGITUDE: longitude,
                }
                return await self.async_step_station()

        return self.async_show_form(
            step_id="coordinates",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LATITUDE): str,
                    vol.Required(CONF_LONGITUDE): str,
                }
            ),
            errors=errors,
        )

    async def async_step_station(self, user_input=None):
        if user_input is not None:
            data = {
                **self._step_one_input,
                CONF_PINNED_STATIONS: user_input.get(CONF_PINNED_STATIONS, []),
            }
            return self.async_create_entry(title=data[CONF_NAME], data=data)

        try:
            center_lat, center_lon = self._resolve_center_for_station_step()
            product = FUEL_TYPE_TO_PRODUCT[self._step_one_input[CONF_FUEL_TYPE]]
            radius = self._step_one_input[CONF_RADIUS]
            client = FuelWatch()
            stations = await self.hass.async_add_executor_job(
                self._fetch_filtered_stations,
                client,
                product,
                center_lat,
                center_lon,
                radius,
            )
        except Exception as err:
            _LOGGER.warning("FuelWatch station fetch failed during setup: %s", err)
            data = {**self._step_one_input, CONF_PINNED_STATIONS: []}
            return self.async_create_entry(title=data[CONF_NAME], data=data)

        if not stations:
            data = {**self._step_one_input, CONF_PINNED_STATIONS: []}
            return self.async_create_entry(title=data[CONF_NAME], data=data)

        options = []
        for s in sorted(stations, key=lambda x: x.get("distance", 0)):
            name = s.get("trading_name", "")
            if not name:
                continue
            label = (
                f"{name} – {s.get('location', '')} "
                f"({s.get('distance', 0):.1f}km) {s.get('price', '')}c"
            )
            options.append({"value": name, "label": label})

        return self.async_show_form(
            step_id="station",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PINNED_STATIONS, default=[]): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options, multiple=True)
                    ),
                }
            ),
            description_placeholders={"count": str(len(options))},
        )

    def _resolve_center_for_station_step(self) -> tuple[float, float]:
        data = self._step_one_input
        location_mode = data.get(CONF_LOCATION_MODE)

        if location_mode == LOCATION_MODE_COORDINATES:
            return float(data[CONF_LATITUDE]), float(data[CONF_LONGITUDE])

        zone_ref = data.get(CONF_ZONE_NAME) or DEFAULT_ZONE_NAME
        entity_id = zone_ref if "." in zone_ref else f"zone.{slugify(zone_ref)}"
        zone = self.hass.states.get(entity_id)
        if zone is None:
            raise ValueError(f"Zone not found: {entity_id}")
        if "latitude" not in zone.attributes or "longitude" not in zone.attributes:
            raise ValueError(f"Zone missing lat/lon: {entity_id}")
        return zone.attributes["latitude"], zone.attributes["longitude"]

    def _fetch_filtered_stations(
        self,
        client: FuelWatch,
        product: int,
        center_lat: float,
        center_lon: float,
        radius: float,
    ) -> list[dict]:
        """Blocking: fetch and normalize stations, filter by radius."""
        client.query(product=product)

        if hasattr(client, "stations"):
            raw = self._normalize_station_objects(client.stations)
        else:
            xml_stations = getattr(client, "xml", None) or getattr(client, "get_xml", None)
            if xml_stations is None:
                return []
            raw = self._normalize_station_dicts(xml_stations)

        filtered = []
        for station in raw:
            try:
                distance = haversine(
                    center_lat,
                    center_lon,
                    float(station["latitude"]),
                    float(station["longitude"]),
                )
                if distance <= radius:
                    station["distance"] = round(distance, 2)
                    filtered.append(station)
            except Exception:
                continue

        return filtered

    def _normalize_station_objects(self, stations) -> list[dict]:
        normalized = []
        for s in stations:
            normalized.append(
                {
                    "price": s.price,
                    "latitude": s.latitude,
                    "longitude": s.longitude,
                    "trading_name": s.trading_name,
                    "address": s.address,
                    "location": s.location,
                    "date": s.date,
                }
            )
        return normalized

    def _normalize_station_dicts(self, stations) -> list[dict]:
        normalized = []
        for s in stations:
            price = s.get("price")
            latitude = s.get("latitude")
            longitude = s.get("longitude")
            if price is None or latitude is None or longitude is None:
                continue
            normalized.append(
                {
                    "price": price,
                    "latitude": latitude,
                    "longitude": longitude,
                    "trading_name": s.get("trading_name") or s.get("trading-name"),
                    "address": s.get("address"),
                    "location": s.get("location"),
                    "date": s.get("date"),
                }
            )
        return normalized

    def _validate_step_one(self, user_input):
        data = dict(user_input)
        errors = {}

        name = data.get(CONF_NAME, "").strip()
        if not name:
            errors[CONF_NAME] = "name_required"
        else:
            data[CONF_NAME] = name

        location_mode = data.get(CONF_LOCATION_MODE, LOCATION_MODE_HOME)
        if location_mode == LOCATION_MODE_HOME:
            data[CONF_ZONE_NAME] = DEFAULT_ZONE_NAME
            data[CONF_LATITUDE] = None
            data[CONF_LONGITUDE] = None
        else:
            data[CONF_ZONE_NAME] = None
            data[CONF_LATITUDE] = None
            data[CONF_LONGITUDE] = None

        return data, errors

    def _parse_coordinate(self, raw_value, field, min_value, max_value, errors):
        value = str(raw_value).strip()
        if not value:
            errors[field] = f"{field}_required"
            return None

        try:
            coordinate = float(value)
        except ValueError:
            errors[field] = f"{field}_invalid"
            return None

        if coordinate < min_value or coordinate > max_value:
            errors[field] = f"{field}_invalid"
            return None

        return coordinate
