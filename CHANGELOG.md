# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-07-09

### Fixed

- Home Assistant no longer logs a `'dict object' has no attribute ...` template
  warning on every published frame for meter fields the RAVEn / EMU-2 never
  reports (for example `current_price`, `network_status`, `link_strength`, and
  `current_period_usage_kwh`). Because the state payload omits values the meter
  has not sent, the generated discovery value templates now guard the lookup
  (`{% if value_json.<key> is defined %}{{ value_json.<key> }}{% endif %}`). An
  absent key renders to an empty string, which Home Assistant ignores for the
  numeric-shaped sensors (leaving them `unknown`) instead of raising.

## [0.1.0] - 2026-06-13

First public release. Bridges a Rainforest Automation RAVEn / EMU-2 serial
device to MQTT with Home Assistant MQTT discovery, after an extended private
dogfooding period.

### Added

- Serial-to-MQTT bridge with Home Assistant MQTT discovery for the RAVEn / EMU-2.
- Recovery-oriented XML stream parser that tolerates partial, malformed, and
  concatenated RAVEn frames.
- Retained MQTT state plus an on-disk state snapshot, so Home Assistant sees
  last-known meter values immediately after a restart.
- `run`, `discovery-json`, and `parse-stdin` CLI subcommands.
- Official multi-arch Docker image (`ghcr.io/lestephen/raven2mqtt`) with a
  `docker run` / Compose quickstart, so deployment needs no host Python, venv,
  udev, or systemd setup.
- systemd unit and udev guidance for the bare-metal / LXC deployment path.
- README "Is this for you?" compatibility matrix that states plainly the bridge
  runs on a separate Linux host and is not installable on Home Assistant OS.

### Reliability

- **Resilient MQTT startup.** The bridge connects asynchronously with automatic
  reconnect and backoff and keeps reading the serial device even when the broker
  is unavailable at startup, instead of crashing on a broker-not-ready race.
- Publishes attempted while disconnected no longer raise or flood the log; the
  disconnect/reconnect transition is logged once.
- Configuration errors (unreadable, malformed, or wrong-typed sections) fail with
  a clear one-line message and exit `EX_CONFIG` (78) instead of a raw traceback.
  The systemd unit will not restart on this permanent-error exit code.

[0.1.0]: https://github.com/lestephen/raven2mqtt/releases/tag/v0.1.0
