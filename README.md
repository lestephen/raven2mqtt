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

## ⚠️ Is this for you?

**`raven2mqtt` is a standalone service that runs on a Linux host owning the
RAVEn USB stick. It is _not_ a Home Assistant add-on or integration, and it
cannot be installed inside Home Assistant OS (HAOS).** You need shell access,
the RAVEn attached to that host, and an MQTT broker Home Assistant already uses
(such as the Mosquitto add-on).

| Your setup | Recommendation |
| --- | --- |
| **Home Assistant OS / Supervised**, RAVEn plugged into the HA machine | The built-in [`rainforest_raven`](https://www.home-assistant.io/integrations/rainforest_raven/) integration, or the one-click [`raven2mqtt` add-on](https://github.com/lestephen/raven2mqtt-addon). |
| **HA in a Docker container**, or a **separate always-on Linux box / LXC / VM** that owns the USB stick | ✅ `raven2mqtt`; run the container (see Quickstart) or a systemd service. |
| RAVEn on a **different machine** than Home Assistant | ✅ `raven2mqtt` on that machine; it reaches HA over MQTT. |

If direct serial access from Home Assistant is stable for you, prefer the
built-in integration. `raven2mqtt` exists for the cases where the serial
lifecycle around HA restarts, upgrades, and USB passthrough is the unreliable
part; see below for why.

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

It also runs as a separate piece of infrastructure you maintain (a container or
service), unlike the built-in integration which runs entirely inside Home
Assistant.

## 🚀 Quickstart (Docker)

The simplest way to run the bridge is the published container image, which needs
no Python, venv, udev, or systemd setup on the host; only Docker on the machine
the RAVEn is plugged into.

1. Create a config from the example and edit it. At minimum set your MQTT broker
   under `[mqtt]` and the serial device path **as it appears inside the
   container** under `[serial] device` (commonly `/dev/ttyACM0` for a RAVEn):

   ```bash
   curl -O https://raw.githubusercontent.com/lestephen/raven2mqtt/main/raven2mqtt.example.toml
   mv raven2mqtt.example.toml raven2mqtt.toml
   # edit raven2mqtt.toml
   ```

2. Run it, passing through the RAVEn USB device (adjust `/dev/ttyACM0` to match
   your host):

   ```bash
   docker run -d --name raven2mqtt \
     --restart unless-stopped \
     --device /dev/ttyACM0 \
     -v "$PWD/raven2mqtt.toml:/config/raven2mqtt.toml:ro" \
     ghcr.io/lestephen/raven2mqtt:latest
   ```

Or with Docker Compose, see [`docker-compose.example.yml`](docker-compose.example.yml):

```yaml
services:
  raven2mqtt:
    image: ghcr.io/lestephen/raven2mqtt:latest
    restart: unless-stopped
    devices:
      - /dev/ttyACM0:/dev/ttyACM0
    volumes:
      - ./raven2mqtt.toml:/config/raven2mqtt.toml:ro
```

The container reads its config from `/config/raven2mqtt.toml`. Home Assistant
discovers the entities over MQTT automatically. To keep last-known state across
container restarts, set `[service] state_file = "/data/state.json"` and add a
`-v raven2mqtt-data:/data` volume (otherwise retained MQTT state still restores
values once Home Assistant reconnects).

## 📦 Install without Docker

Requires Python 3.11+ on the host. The runtime dependencies are `paho-mqtt` and
`pyserial`.

Install the released version as an isolated CLI with [pipx](https://pipx.pypa.io):

```bash
pipx install raven2mqtt
```

Or from source, for development:

```bash
git clone https://github.com/lestephen/raven2mqtt.git
cd raven2mqtt
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest
```

## ⚙️ Configure

Copy the example config and edit it. With Docker this is the file you mount at
`/config/raven2mqtt.toml`; for a host install, `/etc/raven2mqtt.toml` is a
common location:

```bash
cp raven2mqtt.example.toml raven2mqtt.toml
editor raven2mqtt.toml
```

Key settings:

- `[serial] device`: path to the RAVEn serial device. With Docker this is the
  path inside the container (the one you passed with `--device`). On a host,
  `/dev/raven` is a recommended udev symlink (see below).
- `[mqtt]`: broker host, credentials, topic prefix, optional TLS.
- `[service] state_save_interval_seconds`: throttle for `state.json` disk
  writes. The MQTT state topic is published on every meter report regardless;
  this only governs how often the on-disk snapshot is rewritten. Default 60 s.
- `[device]`: identifiers and default entity prefix used by Home Assistant
  MQTT discovery.

Render the Home Assistant discovery payload to verify your configuration:

```bash
raven2mqtt --config raven2mqtt.toml discovery-json
```

## ▶️ Run as a systemd service (advanced: bare-metal or LXC Linux host)

This is the manual path for a standalone Linux host or LXC when you are not
using the Docker image. It needs root, a system user in the `dialout` group, and
a udev rule. **Skip this section entirely if you used the Docker quickstart.**

The unit (`systemd/raven2mqtt.service`) expects a `raven2mqtt` user in the
`dialout` group and a venv at `/opt/raven2mqtt/.venv`:

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

A typical udev rule for a stable `/dev/raven` symlink; adjust the vendor and
product IDs for your specific RAVEn:

```
SUBSYSTEM=="tty", ATTRS{idVendor}=="04b4", ATTRS{idProduct}=="0003", SYMLINK+="raven", GROUP="dialout", MODE="0660"
```

For USB passthrough into an LXC or VM (so the host above can see the device),
see your hypervisor's documentation (for example, Proxmox USB passthrough or an
LXC device cgroup rule). Home Assistant OS cannot satisfy this requirement.

## 🔧 Debugging

These commands require shell access on the host running the bridge (for a
container, prefix with `docker exec raven2mqtt`). Pipe a captured RAVEn stream
through the parser without connecting to MQTT:

```bash
cat raven-capture.log | raven2mqtt parse-stdin
```

Each top-level XML frame is printed as a single JSON line containing `tag`,
`payload`, and the original `raw_xml`. This is useful for diagnosing which
frames the meter is pushing.

## 📄 License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
