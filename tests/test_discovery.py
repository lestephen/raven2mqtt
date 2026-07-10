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


# Required fields are published on every frame (see ``RavenState.update``);
# optional fields come from frames many meters never emit (price, network info,
# current-period usage) and so are absent from every message on those meters.
REQUIRED_COMPONENTS = {"power", "summation_delivered", "summation_received", "last_seen"}
OPTIONAL_COMPONENTS = {
    "current_period_usage",
    "current_price",
    "link_strength",
    "network_status",
}

# Home Assistant ignores an empty rendered value (leaving the entity unchanged /
# unknown) only for sensors that declare a numeric shape via one of these keys.
NUMERIC_SHAPE = {
    "device_class",
    "state_class",
    "unit_of_measurement",
    "suggested_display_precision",
}


def test_optional_value_templates_tolerate_missing_keys() -> None:
    # A real EMU-2 emits only InstantaneousDemand + CurrentSummationDelivered
    # frames, so the price / network / current-period fields never populate and
    # ``RavenState.as_dict`` omits them from every published message. Their
    # templates must render to an empty string instead of raising the
    # "'dict object' has no attribute ..." warning on every frame.
    payload = build_device_discovery_payload(_config())
    # Mirrors the fields a demand+summation-only meter actually publishes.
    sparse = {
        "power_kw": 1.073,
        "summation_delivered_kwh": 120076.706,
        "summation_received_kwh": 0.0,
        "last_seen": "2026-07-09T23:51:07.030554+00:00",
    }

    assert set(payload["cmps"]) == REQUIRED_COMPONENTS | OPTIONAL_COMPONENTS

    for name in OPTIONAL_COMPONENTS:
        component = payload["cmps"][name]
        rendered = _render(component["value_template"], sparse)
        # Absent key renders empty: never raises, never leaks the raw expression.
        assert rendered == "", (name, rendered)
        # An empty string is only safely ignored by HA for numeric-shaped
        # sensors; the sole non-numeric optional component is the network_status
        # diagnostic text sensor, for which an empty state is benign.
        if not NUMERIC_SHAPE.intersection(component):
            assert name == "network_status", (name, sorted(component))

    # Required fields still render their concrete value when present.
    assert _render(payload["cmps"]["power"]["value_template"], sparse) == "1.073"
    assert (
        _render(payload["cmps"]["summation_delivered"]["value_template"], sparse)
        == "120076.706"
    )


def test_required_value_templates_stay_unguarded() -> None:
    # Required fields are unguarded on purpose: if a regression ever drops a core
    # field from the state schema, Home Assistant should surface it rather than
    # silently degrade the entity. Under HA's strict rendering an absent required
    # key raises (which is what logs the visible warning), so we assert the
    # guard was NOT applied to these templates.
    payload = build_device_discovery_payload(_config())

    for name in REQUIRED_COMPONENTS:
        template = payload["cmps"][name]["value_template"]
        assert "is defined" not in template, (name, template)
        try:
            _render(template, {})
        except jinja2.UndefinedError:
            pass
        else:  # pragma: no cover - a required template that swallowed the miss
            raise AssertionError(f"{name} unexpectedly tolerated a missing key")
