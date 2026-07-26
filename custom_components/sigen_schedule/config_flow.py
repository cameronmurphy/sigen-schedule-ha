"""Config flow: email, password, region."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import SigenAuthError, SigenClient
from .const import CONF_REGION, CONF_STATION_ID, DOMAIN, REGION_LABELS

_LOGGER = logging.getLogger(__name__)

REGION_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[
            SelectOptionDict(value=value, label=label)
            for value, label in REGION_LABELS.items()
        ],
        mode=SelectSelectorMode.DROPDOWN,
    )
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_REGION, default="aus"): REGION_SELECTOR,
    }
)


class SigenScheduleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle setting up a Sigenergy account."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            client = SigenClient(
                async_get_clientsession(self.hass),
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                user_input[CONF_REGION],
            )
            try:
                await client.async_login()
                await client.async_fetch_station()
            except SigenAuthError:
                # Nearly always either a typo or the wrong region - ANZ accounts
                # live on `aus`, which is a different shard from `apac`.
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001 - surface anything else as a retry
                _LOGGER.exception("unexpected error connecting to Sigenergy")
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(str(client.station_id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=client.station_name or "Sigenergy",
                    data={**user_input, CONF_STATION_ID: client.station_id},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )
