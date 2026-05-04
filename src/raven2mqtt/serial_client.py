"""Serial reader for RAVEn devices."""

from __future__ import annotations

import logging
import time
from typing import Iterator

from .config import SerialConfig

_LOGGER = logging.getLogger(__name__)


class SerialRavenClient:
    """Read raw chunks from a RAVEn serial terminal."""

    def __init__(self, config: SerialConfig) -> None:
        self._config = config
        self._serial = None

    def __enter__(self) -> "SerialRavenClient":
        import serial

        self._serial = serial.Serial(
            self._config.device,
            baudrate=self._config.baudrate,
            timeout=self._config.read_timeout_seconds,
        )
        self._flush_startup()
        return self

    def __exit__(self, *_args: object) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def chunks(self) -> Iterator[bytes]:
        """Yield raw serial chunks forever."""
        if self._serial is None:
            raise RuntimeError("serial device is not open")
        while True:
            data = self._serial.read(4096)
            if data:
                yield data

    def _flush_startup(self) -> None:
        if self._serial is None:
            return
        deadline = time.monotonic() + self._config.startup_flush_seconds
        while time.monotonic() < deadline:
            self._serial.reset_input_buffer()
            time.sleep(0.25)
        _LOGGER.info("Flushed RAVEn serial input for %.1fs", self._config.startup_flush_seconds)

