"""Editable numeric values for each schedule period."""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DISCHARGE_TYPES, DOMAIN, NUMBER_FIELDS, UNIT_PCT
from .coordinator import SigenScheduleCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one number entity per editable field per period.

    Periods are addressed by index. This integration deliberately does not
    create or delete periods, so the indices stay stable unless the schedule is
    restructured in the mySigen app.
    """
    coordinator: SigenScheduleCoordinator = entry.runtime_data

    entities: list[SigenPeriodNumber] = []
    for index, period in enumerate(coordinator.data or []):
        window_type = period.get("dischargeType")
        for field, spec in NUMBER_FIELDS.items():
            if window_type in spec["types"]:
                entities.append(
                    SigenPeriodNumber(coordinator, entry, index, field, spec)
                )

    async_add_entities(entities)


class SigenPeriodNumber(CoordinatorEntity[SigenScheduleCoordinator], NumberEntity):
    """One editable value on one period of the schedule."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: SigenScheduleCoordinator,
        entry: ConfigEntry,
        index: int,
        field: str,
        spec: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._index = index
        self._field = field
        self._spec = spec

        station_id = coordinator.client.station_id
        self._attr_unique_id = f"{station_id}_period{index}_{field}"
        self._attr_native_unit_of_measurement = spec["unit"]
        self._attr_native_min_value = spec["min"]
        self._attr_native_max_value = spec["max"]
        self._attr_native_step = spec["step"]

        period = coordinator.period_at(index) or {}
        label = DISCHARGE_TYPES.get(period.get("dischargeType"), "Period")
        window = f"{period.get('startTime')}-{period.get('endTime')}"
        self._attr_name = f"{index + 1}. {label} {window} {spec['name']}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(station_id))},
            name=coordinator.client.station_name or "Sigenergy",
            manufacturer="Sigenergy",
            model="Time-of-use schedule",
        )

    @property
    def available(self) -> bool:
        # The period can disappear if the schedule is restructured in the app.
        return super().available and self.coordinator.period_at(self._index) is not None

    @property
    def native_value(self) -> float | None:
        """None means the API has this field unset, i.e. system default."""
        period = self.coordinator.period_at(self._index)
        if not period:
            return None
        value = period.get(self._field)
        return None if value is None else float(value)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        period = self.coordinator.period_at(self._index) or {}
        return {
            "start_time": period.get("startTime"),
            "end_time": period.get("endTime"),
            "days": period.get("whichDay"),
            "window_type": DISCHARGE_TYPES.get(period.get("dischargeType")),
            "api_field": self._field,
            "is_system_default": period.get(self._field) is None,
        }

    async def async_set_native_value(self, value: float) -> None:
        # SOC percentages are whole numbers; power caps keep one decimal.
        coerced = int(value) if self._spec["unit"] == UNIT_PCT else round(value, 1)
        await self.coordinator.async_set_field(self._index, self._field, coerced)
        self.async_write_ha_state()
