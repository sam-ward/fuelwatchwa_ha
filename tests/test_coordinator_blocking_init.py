"""Regression test for a blocking-call warning raised during coordinator setup.

FuelWatchCoordinator.__init__ runs synchronously on the event loop (it is
called directly from sensor.py's async_setup_entry). Constructing the
fuelwatcher.FuelWatch client there triggers fake_useragent's UserAgent(),
which does a blocking importlib-based file read on first instantiation -
tripping Home Assistant's "Detected blocking call to import_module inside
the event loop" guard.

The client must not be constructed until it is actually used, since that
happens inside hass.async_add_executor_job (see _fetch_stations).
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components"))

from fuelwatch_ha.coordinator import FuelWatchCoordinator  # noqa: E402


def _make_coordinator():
    hass = MagicMock()
    config = {"fuel_type": "ULP", "radius": 5}
    return FuelWatchCoordinator(hass, config, "Test Entry")


def test_client_not_constructed_during_init():
    coordinator = _make_coordinator()
    assert coordinator.client is None, (
        "FuelWatch() must not be constructed in __init__: it runs on the "
        "event loop and FuelWatch() triggers a blocking file read via "
        "fake_useragent's UserAgent()."
    )


def test_client_constructed_on_first_fetch():
    coordinator = _make_coordinator()
    coordinator._fetch_stations(product=1)
    assert coordinator.client is not None
