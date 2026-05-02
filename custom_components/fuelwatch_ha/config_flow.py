import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_FUEL_TYPE,
    CONF_LATITUDE,
    CONF_LOCATION_MODE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
    CONF_ZONE_NAME,
    DEFAULT_NAME,
    DEFAULT_RADIUS,
    DEFAULT_ZONE_NAME,
    DOMAIN,
    LOCATION_MODE_COORDINATES,
    LOCATION_MODE_HOME,
    LOCATION_MODE_ZONE,
)

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
                    return self.async_create_entry(
                        title=data[CONF_NAME],
                        data=data,
                    )

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
                data = {
                    **self._step_one_input,
                    CONF_ZONE_NAME: zone_name,
                    CONF_LATITUDE: None,
                    CONF_LONGITUDE: None,
                }
                return self.async_create_entry(
                    title=data[CONF_NAME],
                    data=data,
                )

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
                data = {
                    **self._step_one_input,
                    CONF_ZONE_NAME: DEFAULT_ZONE_NAME,
                    CONF_LATITUDE: latitude,
                    CONF_LONGITUDE: longitude,
                }
                return self.async_create_entry(
                    title=data[CONF_NAME],
                    data=data,
                )

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
