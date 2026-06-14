from raven2mqtt.config import AppConfig, DeviceConfig, MqttConfig, SerialConfig, ServiceConfig
from raven2mqtt.discovery import build_device_discovery_payload, discovery_topic


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
