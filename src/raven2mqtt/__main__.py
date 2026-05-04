"""Command-line entry point for raven2mqtt."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import load_config
from .discovery import build_device_discovery_payload
from .parser import RAVEnXmlStreamParser
from .service import Raven2MqttService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="raven2mqtt")
    parser.add_argument(
        "--config",
        default="raven2mqtt.toml",
        help="Path to TOML config file",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="Run the serial-to-MQTT bridge")
    subparsers.add_parser(
        "discovery-json",
        help="Print the Home Assistant MQTT discovery payload",
    )
    subparsers.add_parser(
        "parse-stdin",
        help="Parse RAVEn XML stream data from stdin and print JSON frames",
    )
    return parser


def _parse_stdin() -> int:
    parser = RAVEnXmlStreamParser()
    for frame in parser.feed(sys.stdin.buffer.read()):
        print(json.dumps(frame.as_dict(), sort_keys=True))
    return 0


def main() -> int:
    args = _build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    if args.command == "parse-stdin":
        return _parse_stdin()

    config = load_config(Path(args.config))

    if args.command == "discovery-json":
        print(json.dumps(build_device_discovery_payload(config), indent=2, sort_keys=True))
        return 0

    if args.command == "run":
        Raven2MqttService(config).run()
        return 0

    raise AssertionError(f"unhandled command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

