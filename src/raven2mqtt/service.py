"""Main raven2mqtt service loop."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from .config import AppConfig
from .models import RavenState
from .mqtt import MqttPublisher
from .parser import RAVEnXmlStreamParser
from .serial_client import SerialRavenClient

_LOGGER = logging.getLogger(__name__)


class Raven2MqttService:
    """Read RAVEn XML frames and publish normalized MQTT state."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._parser = RAVEnXmlStreamParser(encoding=config.serial.encoding)
        self._state_file = Path(config.service.state_file)
        self._state = self._load_state()
        self._mqtt = MqttPublisher(config)
        self._save_interval = max(0.0, config.service.state_save_interval_seconds)
        self._last_save_monotonic: float | None = None

    def run(self) -> None:
        self._mqtt.connect()
        if self._state.last_seen is not None:
            self._mqtt.publish_state(self._state.as_dict())
        try:
            with SerialRavenClient(self._config.serial) as serial_client:
                _LOGGER.info("Reading RAVEn stream from %s", self._config.serial.device)
                for chunk in serial_client.chunks():
                    for frame in self._parser.feed(chunk):
                        self._handle_frame(frame.tag, frame.payload, frame.raw_xml)
        finally:
            self._save_state()
            self._mqtt.close()

    def _handle_frame(self, tag: str, payload: dict, raw_xml: str) -> None:
        _LOGGER.debug("Received RAVEn frame %s", tag)
        self._mqtt.publish_raw({"tag": tag, "payload": payload, "raw_xml": raw_xml})
        changed = self._state.update(tag, payload)

        if tag == "Warning":
            # A warning is an alert: always emit the event, including the first
            # (state-changing) occurrence. Only skip the state publish below when
            # nothing actually changed.
            self._mqtt.publish_event({"type": "warning", "payload": payload})
            if not changed:
                return

        self._mqtt.publish_state(self._state.as_dict())
        self._maybe_save_state(force=changed and self._save_interval == 0.0)

    def _maybe_save_state(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if (
            force
            or self._last_save_monotonic is None
            or (now - self._last_save_monotonic) >= self._save_interval
        ):
            self._save_state()
            self._last_save_monotonic = now

    def _load_state(self) -> RavenState:
        if not self._state_file.exists():
            return RavenState()
        try:
            return RavenState.from_dict(json.loads(self._state_file.read_text()))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as err:
            _LOGGER.warning("Ignoring unreadable state file %s: %s", self._state_file, err)
            return RavenState()

    def _save_state(self) -> None:
        # The on-disk snapshot is best-effort: a full disk, read-only /data, or a
        # bad state_file path must not stop serial-to-MQTT publishing. MQTT
        # retained state remains the primary persistence path.
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._state_file.with_name(self._state_file.name + ".tmp")
            tmp.write_text(json.dumps(self._state.as_dict(), sort_keys=True))
            os.replace(tmp, self._state_file)
        except OSError as err:
            _LOGGER.warning("Could not persist state snapshot to %s: %s", self._state_file, err)
