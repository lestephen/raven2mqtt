import logging

import pytest

from raven2mqtt.config import AppConfig, DeviceConfig, MqttConfig, SerialConfig, ServiceConfig
from raven2mqtt.mqtt import MqttPublisher


class FakeInfo:
    def __init__(self, rc: int) -> None:
        self.rc = rc


class FakeClient:
    """Records paho-mqtt calls. connect() (blocking) simulates a down broker."""

    instances: list["FakeClient"] = []

    def __init__(self, *args, **kwargs) -> None:
        self.calls: list[str] = []
        self.publish_rc = 0
        self.on_connect = None
        self.on_message = None
        self.on_disconnect = None
        FakeClient.instances.append(self)

    def username_pw_set(self, *_a, **_k) -> None:
        self.calls.append("username_pw_set")

    def tls_set(self, *_a, **_k) -> None:
        self.calls.append("tls_set")

    def tls_insecure_set(self, *_a, **_k) -> None:
        self.calls.append("tls_insecure_set")

    def will_set(self, *_a, **_k) -> None:
        self.calls.append("will_set")

    def reconnect_delay_set(self, *_a, **_k) -> None:
        self.calls.append("reconnect_delay_set")

    def connect(self, *_a, **_k) -> None:
        # A blocking connect against an unavailable broker raises this.
        self.calls.append("connect")
        raise ConnectionRefusedError(111, "Connection refused")

    def connect_async(self, *_a, **_k) -> None:
        self.calls.append("connect_async")

    def loop_start(self) -> None:
        self.calls.append("loop_start")

    def loop_stop(self) -> None:
        self.calls.append("loop_stop")

    def disconnect(self) -> None:
        self.calls.append("disconnect")

    def subscribe(self, *_a, **_k) -> None:
        self.calls.append("subscribe")

    def publish(self, *_a, **_k) -> FakeInfo:
        self.calls.append("publish")
        return FakeInfo(self.publish_rc)


@pytest.fixture
def fake_paho(monkeypatch):
    FakeClient.instances.clear()
    monkeypatch.setattr("paho.mqtt.client.Client", FakeClient)
    return FakeClient


def _publisher() -> MqttPublisher:
    return MqttPublisher(
        AppConfig(
            serial=SerialConfig(),
            mqtt=MqttConfig(),
            service=ServiceConfig(),
            device=DeviceConfig(),
        )
    )


def test_connect_does_not_raise_when_broker_unreachable(fake_paho) -> None:
    publisher = _publisher()
    # Must not raise even though a blocking connect() to a down broker would.
    publisher.connect()
    client = fake_paho.instances[-1]
    assert "connect_async" in client.calls
    assert "loop_start" in client.calls
    # The blocking connect() (which raises on a down broker) must not be used.
    assert "connect" not in client.calls


def test_connect_configures_reconnect_backoff(fake_paho) -> None:
    publisher = _publisher()
    publisher.connect()
    client = fake_paho.instances[-1]
    assert "reconnect_delay_set" in client.calls


def test_publish_while_disconnected_does_not_log_per_message_warning(fake_paho, caplog) -> None:
    publisher = _publisher()
    publisher.connect()
    client = fake_paho.instances[-1]
    client.publish_rc = 4  # MQTT_ERR_NO_CONN — broker not connected yet
    with caplog.at_level(logging.WARNING, logger="raven2mqtt.mqtt"):
        for _ in range(5):
            publisher.publish("raven2mqtt/emu2/state", "x", retain=True)
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings == [], f"expected no per-publish warnings while disconnected, got {warnings}"


def test_publish_failure_while_connected_logs_warning(fake_paho, caplog) -> None:
    publisher = _publisher()
    publisher.connect()
    client = fake_paho.instances[-1]
    # Drive the connect callback to mark the session connected.
    publisher._on_connect(client, None, None, 0)
    client.publish_rc = 1  # genuine anomaly while connected
    with caplog.at_level(logging.WARNING, logger="raven2mqtt.mqtt"):
        publisher.publish("raven2mqtt/emu2/state", "x", retain=True)
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1


def test_on_disconnect_logs_single_transition(fake_paho, caplog) -> None:
    publisher = _publisher()
    publisher.connect()
    client = fake_paho.instances[-1]
    publisher._on_connect(client, None, None, 0)
    with caplog.at_level(logging.WARNING, logger="raven2mqtt.mqtt"):
        publisher._on_disconnect(client, None, None, 7, None)
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1
