"""Read-only view of each schedule period."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DISCHARGE_TYPES, DOMAIN, PERIOD_FIELDS
from .coordinator import SigenScheduleCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SigenScheduleCoordinator = entry.runtime_data
    async_add_entities(
        SigenPeriodSensor(coordinator, index)
        for index in range(len(coordinator.data or []))
    )


class SigenPeriodSensor(CoordinatorEntity[SigenScheduleCoordinator], SensorEntity):
    """Shows a period's window and type; the full period is in the attributes."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: SigenScheduleCoordinator, index: int) -> None:
        super().__init__(coordinator)
        self._index = index
        station_id = coordinator.client.station_id
        self._attr_unique_id = f"{station_id}_period{index}"
        self._attr_name = f"{index + 1}. Period"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(station_id))},
            name=coordinator.client.station_name or "Sigenergy",
            manufacturer="Sigenergy",
            model="Time-of-use schedule",
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.period_at(self._index) is not None

    @property
    def native_value(self) -> str | None:
        period = self.coordinator.period_at(self._index)
        if not period:
            return None
        label = DISCHARGE_TYPES.get(period.get("dischargeType"), "Unknown")
        return f"{label} {period.get('startTime')}-{period.get('endTime')}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        period = self.coordinator.period_at(self._index) or {}
        attrs = {key: period.get(key) for key in PERIOD_FIELDS}
        attrs["window_type"] = DISCHARGE_TYPES.get(period.get("dischargeType"))
        return attrs
