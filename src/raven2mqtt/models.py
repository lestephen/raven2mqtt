"""State normalization for RAVEn XML frames."""

from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import fields
from datetime import datetime, timezone
from typing import Any


def _parse_int(value: Any, *, signed: bool = False) -> int | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        if text.lower().startswith("0x"):
            parsed = int(text, 16)
            if signed and parsed & 0x80000000:
                parsed -= 0x100000000
            return parsed
        return int(text)
    except ValueError:
        return None


def _scaled(
    value: Any,
    multiplier: Any,
    divisor: Any,
    *,
    signed: bool = False,
) -> float | None:
    raw = _parse_int(value, signed=signed)
    mult = _parse_int(multiplier) or 1
    div = _parse_int(divisor) or 1
    if raw is None or div == 0:
        return None
    return raw * mult / div


def _price(value: Any, trailing_digits: Any) -> float | None:
    raw = _parse_int(value)
    digits = _parse_int(trailing_digits) or 0
    if raw is None:
        return None
    return raw / (10**digits)


@dataclass
class RavenState:
    """Normalized state built from RAVEn frames."""

    power_kw: float | None = None
    summation_delivered_kwh: float | None = None
    summation_received_kwh: float | None = None
    current_period_usage_kwh: float | None = None
    current_price: float | None = None
    network_status: str | None = None
    network_description: str | None = None
    link_strength: int | None = None
    meter_mac_id: str | None = None
    device_mac_id: str | None = None
    last_frame: str | None = None
    last_warning: str | None = None
    last_seen: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RavenState":
        """Build state from a previously persisted state dictionary."""
        allowed = {field.name for field in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in allowed})

    def update(self, tag: str, payload: dict[str, Any]) -> bool:
        """Update state from a parsed RAVEn payload.

        Returns True if any normalized value actually changed. ``last_seen``
        is refreshed on every call regardless, so callers can publish a
        heartbeat on every frame while persisting only on real changes.
        """
        changed = False
        self.last_frame = tag
        self.last_seen = datetime.now(timezone.utc).isoformat()
        self.raw[tag] = payload

        device_mac = payload.get("DeviceMacId")
        if device_mac:
            changed |= self._assign("device_mac_id", str(device_mac))
        meter_mac = payload.get("MeterMacId")
        if meter_mac:
            changed |= self._assign("meter_mac_id", str(meter_mac))

        if tag == "InstantaneousDemand":
            changed |= self._assign(
                "power_kw",
                _scaled(
                    payload.get("Demand"),
                    payload.get("Multiplier"),
                    payload.get("Divisor"),
                    signed=True,
                ),
            )
        elif tag == "CurrentSummationDelivered":
            changed |= self._assign(
                "summation_delivered_kwh",
                _scaled(
                    payload.get("SummationDelivered"),
                    payload.get("Multiplier"),
                    payload.get("Divisor"),
                ),
            )
            changed |= self._assign(
                "summation_received_kwh",
                _scaled(
                    payload.get("SummationReceived"),
                    payload.get("Multiplier"),
                    payload.get("Divisor"),
                ),
            )
        elif tag == "CurrentPeriodUsage":
            changed |= self._assign(
                "current_period_usage_kwh",
                _scaled(
                    payload.get("CurrentUsage"),
                    payload.get("Multiplier"),
                    payload.get("Divisor"),
                ),
            )
        elif tag == "PriceCluster":
            changed |= self._assign(
                "current_price",
                _price(payload.get("Price"), payload.get("TrailingDigits")),
            )
        elif tag == "NetworkInfo":
            changed |= self._assign("network_status", payload.get("Status"))
            changed |= self._assign("network_description", payload.get("Description"))
            changed |= self._assign("link_strength", _parse_int(payload.get("LinkStrength")))
        elif tag == "Warning":
            changed |= self._assign("last_warning", next(iter(payload.values()), None))

        return changed

    def _assign(self, key: str, value: Any) -> bool:
        if value is None:
            return False
        if getattr(self, key) == value:
            return False
        setattr(self, key, value)
        return True

    def as_dict(self) -> dict[str, Any]:
        """Return a compact JSON-serializable state dict."""
        return {
            key: value
            for key, value in {
                "power_kw": self.power_kw,
                "summation_delivered_kwh": self.summation_delivered_kwh,
                "summation_received_kwh": self.summation_received_kwh,
                "current_period_usage_kwh": self.current_period_usage_kwh,
                "current_price": self.current_price,
                "network_status": self.network_status,
                "network_description": self.network_description,
                "link_strength": self.link_strength,
                "meter_mac_id": self.meter_mac_id,
                "device_mac_id": self.device_mac_id,
                "last_frame": self.last_frame,
                "last_warning": self.last_warning,
                "last_seen": self.last_seen,
            }.items()
            if value is not None
        }
