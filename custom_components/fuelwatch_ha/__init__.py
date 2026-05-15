from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall

from .const import CONF_SCAN_INTERVAL, DOMAIN, SCAN_INTERVAL

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    if not hass.services.has_service(DOMAIN, "refresh"):
        async def handle_refresh(call: ServiceCall) -> None:
            for coordinator in hass.data[DOMAIN].values():
                await coordinator.async_refresh()

        hass.services.async_register(DOMAIN, "refresh", handle_refresh)

    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL),
    )
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator is not None:
        coordinator.update_interval = None if interval == 0 else timedelta(seconds=interval)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, "refresh")

    return unload_ok
