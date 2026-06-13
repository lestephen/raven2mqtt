# raven2mqtt

![tests](https://github.com/lestephen/raven2mqtt/actions/workflows/test.yml/badge.svg)
![python](https://img.shields.io/badge/python-3.11%2B-blue)

Bridge a Rainforest Automation RAVEn / EMU-2 serial device to MQTT and Home
Assistant MQTT discovery.

The RAVEn exposes a simple CDC ACM serial terminal that streams independent XML
fragments. That behavior is awkward inside Home Assistant because every HA
restart can reopen the terminal in the middle of an unsolicited XML report.
This bridge keeps one long-lived serial session outside Home Assistant and
publishes normalized readings over MQTT.

## ⚖️ Relationship to Home Assistant's built-in integration

For many installations, the built-in Home Assistant `rainforest_raven`
integration is the right first choice: it is simple, supported by Home
Assistant's normal configuration flow, and does not require a separate service.

`raven2mqtt` is meant for environments where the RAVEn serial lifecycle is the
unreliable part. The device behaves more like a continuously streaming terminal
than a request/response API. It can emit asynchronous XML reports at any time,
and a process that opens the serial port may start reading in the middle of an
XML fragment. That is especially painful when Home Assistant restarts, upgrades,
reloads an integration, or runs inside a VM with USB passthrough.

This bridge addresses that class of problem by moving serial ownership out of
Home Assistant:

- A small long-running service owns the USB serial terminal continuously.
- Home Assistant restarts and upgrades no longer reopen or reset the RAVEn
  serial session.
- The parser is designed to recover from partial, malformed, or concatenated XML
  fragments without requiring Home Assistant setup retries.
- MQTT retained state lets Home Assistant come back online with the last known
  meter values while waiting for the next RAVEn report.
- Home Assistant consumes normal MQTT discovery entities, so the RAVEn device
  path, Linux permissions, and USB passthrough details stay outside HA Core.

In short: the built-in integration is best when direct serial access is stable.
`raven2mqtt` is for setups where decoupling serial-terminal handling from Home
Assistant makes the system easier to operate.

## ✨ What this bridge does and does not do

`raven2mqtt` is a **passive listener**. It reads whatever XML fragments the
RAVEn pushes asynchronously and normalizes them. It does not currently send
commands to the device, so the entities it can populate depend on what the
meter is configured to broadcast:

| RAVEn frame                  | Populates                                   | Typical cadence       |
| ---------------------------- | ------------------------------------------- | --------------------- |
| `InstantaneousDemand`        | `power_kw`                                  | every 1–8 s           |
| `CurrentSummationDelivered`  | `summation_delivered_kwh`, `summation_received_kwh` | every 5–15 min |
| `CurrentPeriodUsage`         | `current_period_usage_kwh`                  | meter-dependent       |
| `PriceCluster`               | `current_price`                             | meter-dependent       |
| `NetworkInfo`                | `network_status`, `link_strength`           | meter-dependent       |
| `Warning`                    | `last_warning` + MQTT event topic           | as emitted            |

If your RAVEn is paired with a meter that does not push `PriceCluster`,
`NetworkInfo`, or other optional frames, the corresponding Home Assistant
entities will simply remain `unknown`. This is a meter-side behavior, not a
parser limitation.

## 🚀 Install

Requires Python 3.11+. The runtime dependencies are `paho-mqtt` and `pyserial`.

Install the released version as an isolated CLI with [pipx](https://pipx.pypa.io):

```bash
pipx install raven2mqtt
```

Or from source for development:

```bash
git clone https://github.com/lestephen/raven2mqtt.git
cd raven2mqtt
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest
```

## ⚙️ Configure

```bash
cp raven2mqtt.example.toml /etc/raven2mqtt.toml
editor /etc/raven2mqtt.toml
```

Key settings:

- `[serial] device` — path to the RAVEn serial device (`/dev/raven` is a
  recommended udev symlink; see below).
- `[mqtt]` — broker host, credentials, topic prefix, optional TLS.
- `[service] state_save_interval_seconds` — throttle for `state.json` disk
  writes. The MQTT state topic is published on every meter report regardless;
  this only governs how often the on-disk snapshot is rewritten. Default 60 s.
- `[device]` — identifiers and default entity prefix used by Home Assistant
  MQTT discovery.

Render the Home Assistant discovery payload to verify your configuration:

```bash
raven2mqtt --config /etc/raven2mqtt.toml discovery-json
```

## ▶️ Run

```bash
raven2mqtt --config /etc/raven2mqtt.toml run
```

Or as a systemd service — see `systemd/raven2mqtt.service`. The unit expects a
`raven2mqtt` user in the `dialout` group and a venv at `/opt/raven2mqtt/.venv`:

```bash
useradd --system --home /opt/raven2mqtt --shell /usr/sbin/nologin --groups dialout raven2mqtt
install -d -o raven2mqtt -g raven2mqtt /opt/raven2mqtt
python3 -m venv /opt/raven2mqtt/.venv
/opt/raven2mqtt/.venv/bin/pip install /path/to/raven2mqtt
install -m 0644 systemd/raven2mqtt.service /etc/systemd/system/raven2mqtt.service
install -m 0640 -g raven2mqtt raven2mqtt.example.toml /etc/raven2mqtt.toml
editor /etc/raven2mqtt.toml
systemctl daemon-reload
systemctl enable --now raven2mqtt
journalctl -u raven2mqtt -f
```

A typical udev rule for a stable `/dev/raven` symlink — adjust the vendor and
product IDs for your specific RAVEn:

```
SUBSYSTEM=="tty", ATTRS{idVendor}=="04b4", ATTRS{idProduct}=="0003", SYMLINK+="raven", GROUP="dialout", MODE="0660"
```

## 🔧 Debugging

Pipe a captured RAVEn stream through the parser without connecting to MQTT:

```bash
cat raven-capture.log | raven2mqtt parse-stdin
```

Each top-level XML frame is printed as a single JSON line containing `tag`,
`payload`, and the original `raw_xml`. This is useful for diagnosing which
frames the meter is pushing.

## 📄 License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
