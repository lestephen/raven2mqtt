import jinja2

from raven2mqtt.config import AppConfig, DeviceConfig, MqttConfig, SerialConfig, ServiceConfig
from raven2mqtt.discovery import build_device_discovery_payload, discovery_topic


def _config() -> AppConfig:
    return AppConfig(
        serial=SerialConfig(),
        mqtt=MqttConfig(base_topic="raven2mqtt/emu2"),
        service=ServiceConfig(),
        device=DeviceConfig(id="emu2"),
    )


def _render(template: str, value_json: dict) -> str:
    # Mirror Home Assistant's strict template behavior: accessing a missing key
    # on ``value_json`` raises, which is what produces the repeated
    # "'dict object' has no attribute ..." log warnings.
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    return env.from_string(template).render(value_json=value_json)


def test_device_discovery_payload_uses_stable_entity_ids() -> None:
    config = AppConfig(
        serial=SerialConfig(),
        mqtt=MqttConfig(base_topic="raven2mqtt/emu2"),
        service=ServiceConfig(),
        device=DeviceConfig(id="emu2"),
    )

    payload = build_device_discovery_payload(config)

    assert discovery_topic(config) == "homeassistant/device/raven2mqtt_emu2/config"
    assert payload["state_topic"] == "raven2mqtt/emu2/state"
    assert "json_attributes_topic" not in payload
    assert payload["availability"][0]["topic"] == "raven2mqtt/emu2/status"
    assert payload["cmps"]["power"]["default_entity_id"] == "sensor.rainforest_emu_2_power"
    assert payload["cmps"]["summation_delivered"]["state_class"] == "total_increasing"


# Home Assistant ignores an empty rendered value (leaving the entity unchanged /
# unknown) for sensors that declare a numeric shape via one of these keys.
NUMERIC_SHAPE = {
    "device_class",
    "state_class",
    "unit_of_measurement",
    "suggested_display_precision",
}


def test_value_templates_tolerate_missing_keys() -> None:
    # ``RavenState.as_dict`` publishes only the fields seen so far, so any key
    # can be absent from a given state message: optional fields the meter never
    # emits (price / network / current-period) and even core fields during the
    # startup window before their first frame arrives. Every value template must
    # render to an empty string for an absent key instead of raising the
    # "'dict object' has no attribute ..." warning.
    payload = build_device_discovery_payload(_config())

    # Absent everywhere: an empty payload must never raise for any component.
    for name, component in payload["cmps"].items():
        rendered = _render(component["value_template"], {})
        assert rendered == "", (name, rendered)
        # An empty string is only safely ignored by HA for numeric-shaped
        # sensors; the sole non-numeric component is the network_status
        # diagnostic text sensor, for which an empty state is benign.
        if not NUMERIC_SHAPE.intersection(component):
            assert name == "network_status", (name, sorted(component))

    # Present keys still render their concrete value.
    populated = {
        "power_kw": 1.073,
        "summation_delivered_kwh": 120076.706,
        "summation_received_kwh": 0.0,
        "last_seen": "2026-07-09T23:51:07.030554+00:00",
    }
    assert _render(payload["cmps"]["power"]["value_template"], populated) == "1.073"
    assert (
        _render(payload["cmps"]["summation_delivered"]["value_template"], populated)
        == "120076.706"
    )
    assert (
        _render(payload["cmps"]["last_seen"]["value_template"], populated)
        == "2026-07-09T23:51:07.030554+00:00"
    )
