"""Robust parser for RAVEn serial XML fragments."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable
import xml.etree.ElementTree as ET


TOP_LEVEL_TAGS = frozenset(
    {
        "CurrentPeriodUsage",
        "CurrentSummationDelivered",
        "DeviceInfo",
        "InstantaneousDemand",
        "LastPeriodUsage",
        "MessageCluster",
        "MeterInfo",
        "MeterList",
        "NetworkInfo",
        "PriceCluster",
        "ProfileData",
        "ScheduleInfo",
        "TimeCluster",
        "Warning",
    }
)

START_TAG_RE = re.compile(r"<(?P<tag>[A-Za-z_][A-Za-z0-9_.:-]*)(?:\s[^>]*)?>")


@dataclass(frozen=True)
class RavenFrame:
    """A parsed RAVEn XML fragment."""

    tag: str
    payload: dict[str, Any]
    raw_xml: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "payload": self.payload,
            "raw_xml": self.raw_xml,
        }


class RAVEnXmlStreamParser:
    """Incrementally extract top-level RAVEn XML elements from a byte stream."""

    def __init__(
        self,
        *,
        encoding: str = "windows-1252",
        max_buffer_chars: int = 65536,
    ) -> None:
        self._encoding = encoding
        self._max_buffer_chars = max_buffer_chars
        self._buffer = ""

    def feed(self, data: bytes | str) -> list[RavenFrame]:
        """Feed serial bytes and return all complete parsed frames."""
        if isinstance(data, bytes):
            self._buffer += data.decode(self._encoding, errors="replace")
        else:
            self._buffer += data

        frames: list[RavenFrame] = []
        while True:
            if len(self._buffer) > self._max_buffer_chars:
                self._trim_oversized_buffer()

            start = self._find_next_top_level_start()
            if start < 0:
                self._keep_possible_partial_tag()
                return frames
            if start:
                self._buffer = self._buffer[start:]

            match = START_TAG_RE.match(self._buffer)
            if not match:
                return frames

            tag = match.group("tag")
            close = f"</{tag}>"
            end = self._buffer.find(close)
            if end < 0:
                return frames

            end += len(close)
            raw_xml = self._buffer[:end]
            self._buffer = self._buffer[end:]

            try:
                element = ET.fromstring(raw_xml)
            except ET.ParseError:
                continue

            frames.append(
                RavenFrame(
                    tag=element.tag,
                    payload=_element_payload(element),
                    raw_xml=raw_xml,
                )
            )

    def _find_next_top_level_start(self) -> int:
        for match in START_TAG_RE.finditer(self._buffer):
            if match.group("tag") in TOP_LEVEL_TAGS:
                return match.start()
        return -1

    def _keep_possible_partial_tag(self) -> None:
        index = self._buffer.rfind("<")
        if index < 0:
            self._buffer = ""
        else:
            self._buffer = self._buffer[index:]

    def _trim_oversized_buffer(self) -> None:
        self._buffer = self._buffer[-self._max_buffer_chars // 2 :]
        self._keep_possible_partial_tag()


def _element_payload(element: ET.Element) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for child in element:
        value: Any
        if len(child):
            value = _element_payload(child)
        else:
            value = (child.text or "").strip()

        existing = values.get(child.tag)
        if existing is None:
            values[child.tag] = value
        elif isinstance(existing, list):
            existing.append(value)
        else:
            values[child.tag] = [existing, value]
    return values
