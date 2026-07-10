# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-07-09

### Fixed

- The `network_status` diagnostic sensor no longer overwrites a previously
  reported value with a blank string when a state message omits the field.
  Because that text sensor has no numeric shape, Home Assistant does not ignore
  an empty render, so its discovery template now renders `None` (which HA maps
  to `unknown`) for an absent key. Numeric-shaped sensors keep the empty-string
  guard that HA ignores. The value-template guard is now chosen per sensor type
  in `_sensor()`.

## [0.1.1] - 2026-07-09

### Fixed

- Home Assistant no longer logs a `'dict object' has no attribute ...` template
  warning for meter fields that are absent from a published state message. The
  state payload only carries the fields the meter has reported so far, so any
  key can be missing: optional fields the RAVEn / EMU-2 never emits
  (`current_price`, `network_status`, `link_strength`, `current_period_usage_kwh`)
  and even core fields during the startup window before their first frame
  arrives. Every discovery value template now guards the lookup
  (`{% if value_json.<key> is defined %}{{ value_json.<key> }}{% endif %}`), so
  an absent key renders to an empty string, which Home Assistant ignores for the
  numeric-shaped sensors (leaving them `unknown`) instead of raising. A key that
  stops being reported therefore shows as `unknown` in Home Assistant; raven2mqtt
  intentionally does not use per-frame template errors as a field-level health
  signal, since the same absence occurs normally during the startup window
  before a field's first frame arrives.

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
