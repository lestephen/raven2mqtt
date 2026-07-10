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


def test_value_templates_tolerate_missing_keys() -> None:
    # A real EMU-2 often emits only InstantaneousDemand + CurrentSummationDelivered
    # frames, so PriceCluster / NetworkInfo / CurrentPeriodUsage fields never
    # populate. Because the state payload omits None values, those keys are
    # absent from every published message. The discovery value templates must
    # tolerate that instead of raising on the missing key.
    payload = build_device_discovery_payload(_config())
    sparse = {
        "power_kw": 1.073,
        "summation_delivered_kwh": 120076.706,
        "summation_received_kwh": 0.0,
    }

    # Home Assistant ignores an empty rendered value (leaving the entity
    # unchanged / unknown) for sensors that declare a numeric shape via any of
    # these keys, so an absent field must not corrupt their state.
    numeric_shape = {
        "device_class",
        "state_class",
        "unit_of_measurement",
        "suggested_display_precision",
    }

    # Components populated by the sparse payload above.
    populated = {"power", "summation_delivered", "summation_received"}

    for name, component in payload["cmps"].items():
        template = component["value_template"]
        rendered_absent = _render(template, sparse)
        if name in populated:
            continue
        # Absent key must render to an empty string, never raise and never leak
        # the raw ``value_json.<key>`` expression.
        assert rendered_absent == "", (name, rendered_absent)
        # An empty string is only safely ignored by HA when the sensor is
        # numeric-shaped; the sole non-numeric component (network_status) is a
        # diagnostic text sensor for which an empty state is benign.
        if not numeric_shape.intersection(component):
            assert name == "network_status", (name, sorted(component))

    # Present keys still render their concrete value.
    assert _render(payload["cmps"]["power"]["value_template"], sparse) == "1.073"
    assert (
        _render(payload["cmps"]["summation_delivered"]["value_template"], sparse)
        == "120076.706"
    )
