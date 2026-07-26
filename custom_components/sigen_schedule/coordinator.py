"""Coordinator holding the Sigenergy time-of-use schedule."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SigenApiError, SigenAuthError, SigenClient, validate_schedule
from .const import DOMAIN, UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


class SigenScheduleCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Keeps the schedule in sync and serialises writes.

    `batch/save` replaces the entire schedule, so every edit re-posts all
    periods. A lock keeps concurrent edits from racing and clobbering each
    other with stale copies.
    """

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: SigenClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
            config_entry=entry,
        )
        self.client = client
        self._write_lock = asyncio.Lock()

    async def _async_update_data(self) -> list[dict[str, Any]]:
        try:
            return await self.client.async_get_schedule()
        except SigenAuthError as err:
            # Surfaces as a re-auth prompt rather than a silent failure.
            raise UpdateFailed(f"authentication failed: {err}") from err
        except SigenApiError as err:
            raise UpdateFailed(str(err)) from err

    def period_at(self, index: int) -> dict[str, Any] | None:
        if not self.data or index >= len(self.data):
            return None
        return self.data[index]

    async def async_set_field(self, index: int, field: str, value: float) -> None:
        """Change one numeric field on one period and save the whole schedule."""
        async with self._write_lock:
            if not self.data:
                raise HomeAssistantError("no schedule loaded yet")
            if index >= len(self.data):
                raise HomeAssistantError(
                    f"period {index} no longer exists - the schedule changed "
                    "in the mySigen app"
                )

            periods = [dict(period) for period in self.data]
            previous = periods[index].get(field)
            periods[index][field] = value

            problems = validate_schedule(periods)
            if problems:
                raise HomeAssistantError(
                    "refusing to write an invalid schedule: " + "; ".join(problems)
                )

            try:
                await self.client.async_save_schedule(periods)
            except (SigenApiError, SigenAuthError) as err:
                raise HomeAssistantError(f"failed to save schedule: {err}") from err

            _LOGGER.debug(
                "period %s %s: %s -> %s", index, field, previous, value
            )
            # Show the new value immediately, then reconcile against the API.
            self.async_set_updated_data(periods)

        await self.async_request_refresh()
