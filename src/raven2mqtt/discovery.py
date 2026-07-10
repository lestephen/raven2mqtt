"""Home Assistant MQTT discovery payload generation."""

from __future__ import annotations

from typing import Any

from . import __version__
from .config import AppConfig


def _sensor(
    *,
    unique_id: str,
    name: str,
    key: str,
    default_entity_id: str,
    unit: str | None = None,
    device_class: str | None = None,
    state_class: str | None = None,
    entity_category: str | None = None,
    suggested_display_precision: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "p": "sensor",
        "unique_id": unique_id,
        "name": name,
        "default_entity_id": default_entity_id,
        # ``RavenState.as_dict`` publishes only the fields the meter has reported
        # so far, so ANY key can be absent from a given state message: optional
        # fields the meter never emits (price, network info, current-period
        # usage), and even core fields during the startup window before their
        # first frame arrives. Guard every lookup so a missing key renders to an
        # empty string instead of raising a ``'dict object' has no attribute ...``
        # warning on that frame. Home Assistant ignores an empty render for the
        # numeric-shaped sensors, leaving them ``unknown``. A field that stops
        # being reported shows as ``unknown`` in HA; the same absence happens
        # normally during startup, so per-frame template errors are not used as a
        # field-level health signal.
        "value_template": (
            f"{{% if value_json.{key} is defined %}}{{{{ value_json.{key} }}}}{{% endif %}}"
        ),
    }
    if unit is not None:
        payload["unit_of_measurement"] = unit
    if device_class is not None:
        payload["device_class"] = device_class
    if state_class is not None:
        payload["state_class"] = state_class
    if entity_category is not None:
        payload["entity_category"] = entity_category
    if suggested_display_precision is not None:
        payload["suggested_display_precision"] = suggested_display_precision
    return payload


def discovery_topic(config: AppConfig) -> str:
    """Return the retained Home Assistant device-discovery topic."""
    return f"{config.mqtt.discovery_prefix}/device/raven2mqtt_{config.device.id}/config"


def build_device_discovery_payload(config: AppConfig) -> dict[str, Any]:
    """Build a Home Assistant MQTT device-discovery payload."""
    base_unique = f"raven2mqtt_{config.device.id}"
    entity_prefix = config.device.default_entity_prefix
    device: dict[str, Any] = {
        "identifiers": [base_unique],
        "name": config.device.name,
        "manufacturer": config.device.manufacturer,
        "model": config.device.model,
    }
    if config.device.serial_number:
        device["serial_number"] = config.device.serial_number
    if config.device.sw_version:
        device["sw_version"] = config.device.sw_version

    return {
        "device": device,
        "origin": {
            "name": "raven2mqtt",
            "sw_version": __version__,
            "support_url": "https://github.com/lestephen/raven2mqtt",
        },
        "availability": [{"topic": config.mqtt.availability_topic}],
        "availability_mode": "latest",
        "state_topic": config.mqtt.state_topic,
        "qos": 0,
        "cmps": {
            "power": _sensor(
                unique_id=f"{base_unique}_power",
                name="Power",
                key="power_kw",
                default_entity_id=f"sensor.{entity_prefix}_power",
                unit="kW",
                device_class="power",
                state_class="measurement",
                suggested_display_precision=3,
            ),
            "summation_delivered": _sensor(
                unique_id=f"{base_unique}_summation_delivered",
                name="Summation delivered",
                key="summation_delivered_kwh",
                default_entity_id=f"sensor.{entity_prefix}_summation_delivered",
                unit="kWh",
                device_class="energy",
                state_class="total_increasing",
                suggested_display_precision=3,
            ),
            "summation_received": _sensor(
                unique_id=f"{base_unique}_summation_received",
                name="Summation received",
                key="summation_received_kwh",
                default_entity_id=f"sensor.{entity_prefix}_summation_received",
                unit="kWh",
                device_class="energy",
                state_class="total_increasing",
                suggested_display_precision=3,
            ),
            "current_period_usage": _sensor(
                unique_id=f"{base_unique}_current_period_usage",
                name="Current period usage",
                key="current_period_usage_kwh",
                default_entity_id=f"sensor.{entity_prefix}_current_period_usage",
                unit="kWh",
                device_class="energy",
                state_class="total",
                suggested_display_precision=3,
            ),
            "current_price": _sensor(
                unique_id=f"{base_unique}_current_price",
                name="Current price",
                key="current_price",
                default_entity_id=f"sensor.{entity_prefix}_current_price",
                state_class="measurement",
                suggested_display_precision=4,
            ),
            "link_strength": _sensor(
                unique_id=f"{base_unique}_link_strength",
                name="Link strength",
                key="link_strength",
                default_entity_id=f"sensor.{entity_prefix}_link_strength",
                unit="%",
                entity_category="diagnostic",
            ),
            "network_status": _sensor(
                unique_id=f"{base_unique}_network_status",
                name="Network status",
                key="network_status",
                default_entity_id=f"sensor.{entity_prefix}_network_status",
                entity_category="diagnostic",
            ),
            "last_seen": _sensor(
                unique_id=f"{base_unique}_last_seen",
                name="Last seen",
                key="last_seen",
                default_entity_id=f"sensor.{entity_prefix}_last_seen",
                device_class="timestamp",
                entity_category="diagnostic",
            ),
        },
    }
