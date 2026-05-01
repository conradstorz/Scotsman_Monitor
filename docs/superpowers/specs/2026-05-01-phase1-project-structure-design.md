# Phase 1 Project Structure Design

**Date:** 2026-05-01  
**Scope:** Phase 1 only — sensor logging, Pi health, SQLite, Loguru, basic FastAPI dashboard, Tailscale remote access, systemd service, repeatable Pi setup scripts.  
**Approach:** Option B — hierarchical structure from day one, numbered setup scripts.

---

## Repository Root Layout

```
scotsman_monitor/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── .env.example              ← documents all required secrets, no values
│
├── config/
│   ├── config.example.toml   ← full example with every field documented, committed to git
│   └── config.local.toml     ← machine-specific values, gitignored
│
├── scripts/                  ← numbered bash setup scripts
├── systemd/                  ← systemd unit file
├── src/ice_gateway/          ← Python application
├── tests/                    ← mirrors src structure
├── data/                     ← runtime SQLite and raw captures, gitignored
└── logs/                     ← runtime Loguru logs, gitignored
```

`config.example.toml` is committed to git and documents every available field with safe defaults. `config.local.toml` is the machine-specific config and is gitignored. `06_deploy_app.sh` copies the example to `config.local.toml` as a starting point if it does not already exist.

**Note:** The existing `config/ksbun_gateway.toml` in the repo is a partial early draft. It will be replaced by `config.example.toml` (committed) and `config.local.toml` (gitignored) during implementation.

`data/` and `logs/` contain `.gitkeep` files so the directories exist in the repo but their runtime contents are never committed.

---

## Setup Scripts

Fresh Raspbian install assumed each time. No idempotency required.

```
scripts/
├── 00_README.sh          ← prints install order and verifies repo is present
├── 01_setup_os.sh        ← apt update/upgrade, base packages, timezone, SSH
├── 02_setup_network.sh   ← static IP on eth0 for KSBU-N private subnet
├── 03_setup_tailscale.sh ← install Tailscale, prompt for auth key, tailscale up
├── 04_setup_onewire.sh   ← enable 1-wire overlay in /boot/firmware/config.txt
├── 05_setup_python.sh    ← install uv, uv sync
└── 06_deploy_app.sh      ← copy configs, install systemd unit, enable and start service
```

**Network layout established by `02_setup_network.sh`:**
- `wlan0` — DHCP from site router, internet access, Tailscale
- `eth0` — static `192.168.50.1/24`, private KSBU-N link only, no internet exposure

**`01_setup_os.sh` installs:** `git`, `sqlite3`, `i2c-tools`, `chrony`, `ufw`, `openssh-server`

**`04_setup_onewire.sh`** appends `dtoverlay=w1-gpio` to `/boot/firmware/config.txt` and enables the kernel modules. Default GPIO pin is GPIO4.

**`06_deploy_app.sh`** copies `config.example.toml` → `config.local.toml` and `.env.example` → `.env` if those files do not already exist, then installs and starts the systemd service.

---

## Python Application Structure

```
src/ice_gateway/
├── __init__.py
├── main.py               ← entry point: wires components, starts polling + dashboard
├── config.py             ← pydantic-settings: loads config.local.toml + .env secrets
├── constants.py          ← enums: ReadQuality (ok, crc_error, impossible_value, missing, bus_fault)
├── logging_setup.py      ← configures all Loguru sinks with rotation policy
├── models.py             ← Pydantic data models: SensorReading, PiHealth, SensorConfig
├── database.py           ← SQLAlchemy engine, session factory, table creation on startup
│
├── sensors/
│   ├── __init__.py
│   ├── base.py           ← SensorBusReader ABC (hardware abstraction boundary)
│   ├── onewire.py        ← production reader: walks /sys/bus/w1/devices/
│   └── pi_health.py      ← psutil: CPU temp, memory %, disk %, network interfaces
│
├── dashboard/
│   ├── __init__.py
│   ├── app.py            ← FastAPI app factory, mounts routes and static files
│   ├── routes.py         ← GET / → overview.html; GET /api/temperatures and GET /api/health return JSON
│   ├── templates/
│   │   ├── base.html     ← shared layout, nav
│   │   └── overview.html ← live sensor readings + Pi health summary
│   └── static/           ← plain CSS only, no JS framework, no build step
│
└── tasks/
    ├── __init__.py
    └── polling.py        ← asyncio loop: reads sensors, writes DB, evaluates health
```

**Structural rules:**

- `main.py` is wiring only: loads config, sets up logging, creates DB, injects real `SensorBusReader`, starts polling task and Uvicorn. No business logic.
- `AppConfig` is instantiated once in `main.py` and passed into every component via constructor arguments. Nothing imports config directly.
- `sensors/base.py` defines `SensorBusReader` ABC at Phase 1. Every future hardware boundary (UPS, KSBU-N, GPIO) follows the same pattern.
- `dashboard/static/` is plain CSS only. HTMX can be added as a single script tag in a later phase if live refresh is needed.
- `tasks/polling.py` is a single file for Phase 1. `retention.py` and `heartbeat.py` are added as siblings in later phases.

**`main.py` startup sequence:**

```
1. Load AppConfig              ← exits with clear error if this fails
2. Configure Loguru sinks      ← exits with clear error if this fails
3. Create/verify SQLite tables ← exits with clear error if this fails
4. Instantiate SensorBusReader
5. Start polling loop (asyncio task)
6. Start Uvicorn
```

Steps 1–3 are hard failures. Steps 4–6: if the sensor bus is unavailable at startup, the polling loop logs the error and retries on the next cycle rather than crashing.

---

## Test Structure

```
tests/
├── conftest.py                     ← shared fixtures
├── test_config.py                  ← loads valid TOML, rejects bad input
├── test_models.py                  ← each model accepts valid / rejects invalid data
│
├── fixtures/
│   ├── config_valid.toml           ← known-good config for test_config.py
│   └── config_missing_field.toml   ← known-bad config for validation tests
│
├── sensors/
│   ├── test_onewire.py             ← normal read, missing sensor, CRC error, bus failure
│   └── test_pi_health.py           ← CPU/mem/disk stats read and stored correctly
│
└── dashboard/
    └── test_routes.py              ← every route returns 200 via FastAPI TestClient
```

**`conftest.py` provides four shared fixtures:**

| Fixture | Purpose |
|---|---|
| `db_session` | In-memory SQLite session, rolled back after each test |
| `fake_sensor_bus(readings)` | Injectable `SensorBusReader` returning scripted readings or errors |
| `app_client` | FastAPI `TestClient` with `fake_sensor_bus` injected |
| `valid_config` | Loaded `AppConfig` from `fixtures/config_valid.toml` |

No test touches the real filesystem for data, the real sensor bus, or real network interfaces. All hardware is injected via the `SensorBusReader` ABC. The `fixtures/` directory grows in Phase 2 when KSBU-N HTML snapshots are needed for parser tests.

---

## Configuration and Data Flow

**Configuration loading chain:**

```
config.local.toml + .env
        ↓
config.py (pydantic-settings)
        ↓
AppConfig (passed by constructor everywhere)
```

**Runtime data flow:**

```
/sys/bus/w1/devices/
        ↓
onewire.py (SensorBusReader)
        ↓
polling.py (asyncio, every 30s)
        ├── SensorReading rows → data/ice_gateway.sqlite
        └── PiHealth rows     → data/ice_gateway.sqlite
                                        ↓
                                  routes.py (FastAPI)
                                        ↓
                                  overview.html (Jinja2)
                                        ↓
                            browser over LAN / Tailscale
```

**Loguru sinks** are configured in `logging_setup.py` at startup:
- `logs/sensors.log` — sensor readings, missing/new sensor events
- `logs/ice_gateway.log` — application lifecycle, dashboard requests

Rotation policy: daily rotation, compress old logs, retain 365 days.

---

## Phase 1 Deliverable

From a remote computer over Tailscale, the operator can:
- Open the dashboard
- See live DS18B20 temperature readings
- See Pi CPU/memory/disk health
- Confirm data is being written to the local SQLite database

Test deliverable: `conftest.py`, `test_config.py`, `test_models.py`, `sensors/test_onewire.py`, `sensors/test_pi_health.py`, `dashboard/test_routes.py` all passing. Coverage ≥ 80% on `src/ice_gateway/`.

---

## What Phase 1 Deliberately Excludes

- KSBU-N communication (Phase 2)
- Alert channels: email, SMS, MQTT (Phase 3)
- UPS / safe shutdown (Phase 4)
- Relay outputs and expansion I/O (Phase 5)
- Reporting, maintenance log, offsite backup (Phase 6)
