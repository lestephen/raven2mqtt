"""MQTT publishing helpers."""

from __future__ import annotations

import json
import logging
from typing import Any

from .config import AppConfig
from .discovery import build_device_discovery_payload, discovery_topic

_LOGGER = logging.getLogger(__name__)


class MqttPublisher:
    """Small wrapper around paho-mqtt."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._client = None
        self._connected = False
        self._ha_status_topic = "homeassistant/status"

    def connect(self) -> None:
        import paho.mqtt.client as mqtt

        if hasattr(mqtt, "CallbackAPIVersion"):
            self._client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=self._config.mqtt.client_id,
            )
        else:
            self._client = mqtt.Client(client_id=self._config.mqtt.client_id)
        if self._config.mqtt.username:
            self._client.username_pw_set(
                self._config.mqtt.username,
                self._config.mqtt.password or None,
            )
        if self._config.mqtt.tls_enabled:
            ca = self._config.mqtt.tls_ca or None
            self._client.tls_set(ca_certs=ca)
            if self._config.mqtt.tls_insecure:
                self._client.tls_insecure_set(True)
        self._client.will_set(
            self._config.mqtt.availability_topic,
            payload="offline",
            retain=True,
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect
        # Let paho's network loop own the entire connection lifecycle, including
        # the initial connect, and retry with exponential backoff. A broker that
        # is not yet up at startup must not crash the bridge — the serial reader
        # keeps running and publishes resume once the broker appears.
        self._client.reconnect_delay_set(min_delay=1, max_delay=60)
        _LOGGER.info(
            "Connecting to MQTT broker %s:%s",
            self._config.mqtt.host,
            self._config.mqtt.port,
        )
        self._client.connect_async(self._config.mqtt.host, self._config.mqtt.port)
        self._client.loop_start()

    def close(self) -> None:
        if self._client is None:
            return
        try:
            self.publish_availability(False)
        except Exception as err:  # noqa: BLE001 - shutdown best effort
            _LOGGER.debug("Suppressing publish_availability error during close: %s", err)
        self._client.loop_stop()
        self._client.disconnect()

    def _on_connect(self, client: Any, _userdata: Any, _flags: Any, reason_code: Any, *_args: Any) -> None:
        rc = getattr(reason_code, "value", reason_code)
        if rc != 0:
            # Initial/async connect attempts that fail keep retrying via paho's
            # network loop; surface the reason once so a misconfigured broker is
            # diagnosable rather than a silent background retry.
            _LOGGER.warning("MQTT connect failed: rc=%s", rc)
            return
        self._connected = True
        _LOGGER.info("MQTT connected; (re)subscribing and republishing discovery")
        client.subscribe(self._ha_status_topic)
        self.publish_discovery()
        self.publish_availability(True)

    def _on_disconnect(self, _client: Any, _userdata: Any, *_args: Any) -> None:
        # paho will auto-reconnect; log the transition once instead of emitting a
        # warning per dropped publish while the broker is away.
        if self._connected:
            _LOGGER.warning("MQTT disconnected; auto-reconnecting and will republish on reconnect")
        self._connected = False

    def _on_message(self, _client: Any, _userdata: Any, message: Any) -> None:
        if message.topic == self._ha_status_topic and message.payload == b"online":
            _LOGGER.info("Home Assistant birth message received; republishing discovery")
            self.publish_discovery()

    def publish_availability(self, online: bool) -> None:
        self.publish(
            self._config.mqtt.availability_topic,
            "online" if online else "offline",
            retain=True,
        )

    def publish_discovery(self) -> None:
        self.publish(
            discovery_topic(self._config),
            build_device_discovery_payload(self._config),
            retain=True,
        )

    def publish_state(self, state: dict[str, Any]) -> None:
        self.publish(
            self._config.mqtt.state_topic,
            state,
            retain=self._config.mqtt.retain_state,
        )

    def publish_raw(self, frame: dict[str, Any]) -> None:
        self.publish(self._config.mqtt.raw_topic, frame, retain=False)

    def publish_event(self, event: dict[str, Any]) -> None:
        self.publish(self._config.mqtt.event_topic, event, retain=False)

    def publish(self, topic: str, payload: dict[str, Any] | str, *, retain: bool) -> None:
        if self._client is None:
            raise RuntimeError("MQTT client is not connected")
        encoded = json.dumps(payload, separators=(",", ":")) if isinstance(payload, dict) else payload
        info = self._client.publish(topic, encoded, retain=retain)
        rc = getattr(info, "rc", 0)
        # While disconnected, publishes are expected to fail; the disconnect was
        # already logged once. Only warn when a publish fails on a live session.
        if rc != 0 and self._connected:
            _LOGGER.warning("MQTT publish to %s failed: rc=%s", topic, rc)
