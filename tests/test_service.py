import json

import pytest

from raven2mqtt.config import AppConfig, DeviceConfig, MqttConfig, SerialConfig, ServiceConfig
from raven2mqtt.service import Raven2MqttService


def _build_service(tmp_path, *, save_interval: float = 60.0) -> Raven2MqttService:
    config = AppConfig(
        serial=SerialConfig(),
        mqtt=MqttConfig(),
        service=ServiceConfig(
            state_file=str(tmp_path / "state.json"),
            state_save_interval_seconds=save_interval,
        ),
        device=DeviceConfig(),
    )
    return Raven2MqttService(config)


class _FakeMqtt:
    def __init__(self) -> None:
        self.raw: list = []
        self.events: list = []
        self.states: list = []

    def publish_raw(self, frame) -> None:
        self.raw.append(frame)

    def publish_event(self, event) -> None:
        self.events.append(event)

    def publish_state(self, state) -> None:
        self.states.append(state)


def test_new_warning_publishes_event(tmp_path) -> None:
    service = _build_service(tmp_path)
    service._mqtt = _FakeMqtt()
    service._handle_frame(
        "Warning",
        {"Text": "meter tamper"},
        "<Warning><Text>meter tamper</Text></Warning>",
    )
    assert any(e.get("type") == "warning" for e in service._mqtt.events), (
        "a new warning must publish a warning event, not only repeated ones"
    )


def test_save_state_failure_is_nonfatal(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, save_interval=0.0)
    service._mqtt = _FakeMqtt()

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr("raven2mqtt.service.os.replace", boom)
    # A failed state snapshot (full disk, read-only /data) must not crash the
    # serial-to-MQTT path.
    service._handle_frame(
        "InstantaneousDemand",
        {"Demand": "0x000004D2", "Multiplier": "0x00000001", "Divisor": "0x000003E8"},
        "<InstantaneousDemand/>",
    )
    assert service._mqtt.states, "state should still be published to MQTT despite the snapshot failure"


def test_save_state_writes_atomically(tmp_path) -> None:
    service = _build_service(tmp_path)
    service._state.update(
        "InstantaneousDemand",
        {"Demand": "0x000004D2", "Multiplier": "0x00000001", "Divisor": "0x000003E8"},
    )

    service._save_state()

    state_path = tmp_path / "state.json"
    assert state_path.exists()
    assert not (tmp_path / "state.json.tmp").exists()
    assert json.loads(state_path.read_text())["power_kw"] == 1.234


def test_throttle_defers_writes_inside_interval(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, save_interval=60.0)
    fake_now = [1000.0]
    monkeypatch.setattr("raven2mqtt.service.time.monotonic", lambda: fake_now[0])

    saves: list[float] = []
    monkeypatch.setattr(service, "_save_state", lambda: saves.append(fake_now[0]))

    service._maybe_save_state()
    fake_now[0] = 1010.0
    service._maybe_save_state()
    fake_now[0] = 1075.0
    service._maybe_save_state()

    assert saves == [1000.0, 1075.0]


def test_throttle_zero_interval_writes_every_call(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, save_interval=0.0)
    fake_now = [1000.0]
    monkeypatch.setattr("raven2mqtt.service.time.monotonic", lambda: fake_now[0])

    saves: list[float] = []
    monkeypatch.setattr(service, "_save_state", lambda: saves.append(fake_now[0]))

    service._maybe_save_state()
    service._maybe_save_state()

    assert saves == [1000.0, 1000.0]
