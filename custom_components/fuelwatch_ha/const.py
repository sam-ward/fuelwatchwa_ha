DOMAIN = "fuelwatch_ha"

CONF_FUEL_TYPE = "fuel_type"
CONF_LATITUDE = "latitude"
CONF_LOCATION_MODE = "location_mode"
CONF_LONGITUDE = "longitude"
CONF_NAME = "name"
CONF_PINNED_STATIONS = "pinned_stations"
CONF_RADIUS = "radius"
CONF_ZONE_NAME = "zone_name"

DEFAULT_NAME = "Home"
DEFAULT_RADIUS = 10  # km
DEFAULT_ZONE_NAME = "home"

LOCATION_MODE_HOME = "home_zone"
LOCATION_MODE_ZONE = "zone"
LOCATION_MODE_COORDINATES = "coordinates"

LOCATION_MODE_OPTIONS = [
    LOCATION_MODE_HOME,
    LOCATION_MODE_ZONE,
    LOCATION_MODE_COORDINATES,
]

SCAN_INTERVAL = 3600  # 1hr

FUEL_TYPE_TO_PRODUCT = {
    "ULP": 1,
    "PULP": 2,
    "Diesel": 4,
    "LPG": 5,
    "98RON": 6,
    "E85": 10,
    "Brand Diesel": 11,
}
