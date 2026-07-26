"""The Sigenergy Schedule integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SigenApiError, SigenAuthError, SigenClient
from .const import CONF_REGION
from .coordinator import SigenScheduleCoordinator

PLATFORMS = [Platform.NUMBER, Platform.SENSOR]

type SigenConfigEntry = ConfigEntry[SigenScheduleCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SigenConfigEntry) -> bool:
    """Set up Sigenergy Schedule from a config entry."""
    client = SigenClient(
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_REGION],
    )

    try:
        await client.async_login()
        await client.async_fetch_station()
    except SigenAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except SigenApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = SigenScheduleCoordinator(hass, entry, client)
    # Entities are built from the periods that exist, so the first load has to
    # succeed before we forward to the platforms.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SigenConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
