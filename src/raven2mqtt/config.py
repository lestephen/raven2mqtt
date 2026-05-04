"""Configuration loading for raven2mqtt."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class SerialConfig:
    device: str = "/dev/raven"
    baudrate: int = 115200
    read_timeout_seconds: float = 1.0
    startup_flush_seconds: float = 3.0
    encoding: str = "windows-1252"


@dataclass(frozen=True)
class MqttConfig:
    host: str = "localhost"
    port: int = 1883
    username: str = ""
    password: str = ""
    client_id: str = "raven2mqtt-emu2"
    base_topic: str = "raven2mqtt/emu2"
    discovery_prefix: str = "homeassistant"
    retain_state: bool = True
    tls_enabled: bool = False
    tls_ca: str = ""
    tls_insecure: bool = False

    @property
    def state_topic(self) -> str:
        return f"{self.base_topic}/state"

    @property
    def availability_topic(self) -> str:
        return f"{self.base_topic}/status"

    @property
    def raw_topic(self) -> str:
        return f"{self.base_topic}/raw"

    @property
    def event_topic(self) -> str:
        return f"{self.base_topic}/event"


@dataclass(frozen=True)
class DeviceConfig:
    id: str = "emu2"
    name: str = "Rainforest EMU-2"
    manufacturer: str = "Rainforest Automation"
    model: str = "EMU-2"
    serial_number: str = ""
    sw_version: str = ""
    default_entity_prefix: str = "rainforest_emu_2"


@dataclass(frozen=True)
class ServiceConfig:
    state_file: str = "/var/lib/raven2mqtt/state.json"
    state_save_interval_seconds: float = 60.0


@dataclass(frozen=True)
class AppConfig:
    serial: SerialConfig
    mqtt: MqttConfig
    service: ServiceConfig
    device: DeviceConfig


def _section(data: dict, name: str) -> dict:
    section = data.get(name, {})
    if not isinstance(section, dict):
        raise ValueError(f"[{name}] must be a table")
    return section


def load_config(path: Path) -> AppConfig:
    """Load TOML config from path."""
    data = tomllib.loads(path.read_text()) if path.exists() else {}
    return AppConfig(
        serial=SerialConfig(**_section(data, "serial")),
        mqtt=MqttConfig(**_section(data, "mqtt")),
        service=ServiceConfig(**_section(data, "service")),
        device=DeviceConfig(**_section(data, "device")),
    )
