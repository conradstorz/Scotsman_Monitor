# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

Raspberry Pi 4 based monitoring gateway for a Scotsman Prodigy ice machine with a KSBU-N Smart-Board. Logs DS18B20 temperature sensors, communicates with the machine controller, provides a FastAPI dashboard, and sends multi-channel alerts. Intended to run as a systemd service on-site with Tailscale remote access.

**Core design rule:** Independent sensors are the truth for environmental conditions. The KSBU-N is the truth for machine controller state. The Pi is the historian, alert manager, dashboard, and remote access bridge.

The full project specification is in `scotsman_ice_gateway_complete_spec.md`.

## Commands

```bash
# Install dependencies
uv sync

# Run application
uv run python main.py

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/ice_gateway --cov-report=term-missing --cov-fail-under=80

# Run a single test file
uv run pytest tests/sensors/test_onewire.py

# Lint
uv run ruff check src/ tests/

# Format check
uv run ruff format --check src/ tests/

# Type check (strict)
uv run mypy src/ice_gateway --strict --no-error-summary
```

## Planned Architecture

The project is currently in early development. The spec defines this module layout under `src/ice_gateway/`:

- **`sensors/`** — DS18B20 One-Wire bus (`onewire.py`), Pi CPU/memory health (`pi_health.py`), UPS battery/power state (`ups.py`). All hardware-touching code must sit behind an ABC so tests can inject fakes without hardware.
- **`ksbu/`** — KSBU-N Smart-Board communication. Primary path: NAFEM protocol client. Fallback: web interface scraper (`web_client.py`). Parser is a pure function (HTML/JSON → structured status) with no I/O, testable against static HTML fixtures in `tests/fixtures/`.
- **`alerts/`** — Alert manager with deduplication, cooldown, escalation. Dedup key: `(category, source, severity)`. Channels: email, SMS (Twilio stub), MQTT, webhook.
- **`dashboard/`** — FastAPI + Jinja2 dashboard. Access only over LAN or Tailscale. Never public.
- **`tasks/`** — Polling loops, retention cleanup, heartbeat, backup.
- **`config.py`** — Pydantic-settings loading from TOML (`config/ksbun_gateway.toml`). Secrets always from `.env` or environment variables, never in the TOML file.
- **`database.py`** — SQLite via SQLAlchemy/SQLModel. DB at `data/ice_gateway.sqlite`. Raw KSBU snapshots at `data/raw_ksbu/`.

## Hardware Abstraction Requirement

Every hardware boundary must have an ABC that production code depends on via constructor injection — not import-time globals. This is the most important structural rule for keeping tests fast and hardware-free:

- `SensorBusReader` — wraps `/sys/bus/w1/devices/` reads
- `UPSStatusProvider` — wraps I2C HAT reads
- `NetworkChecker` — wraps Tailscale/internet/KSBU reachability checks
- `KSBUNTransport` — wraps both NAFEM and web clients
- `GPIOController` — wraps relay/digital I/O

## Configuration

- Primary format: **TOML** (`config/ksbun_gateway.toml`)
- Secrets: `.env` file or `systemd EnvironmentFile` — never in TOML
- Per the spec, `pydantic-settings` loads the TOML and accepts environment-variable overrides

## Code Style

- Use `pathlib` for all paths
- Use Pydantic v2 for schemas and config
- Use Loguru for all logging (not stdlib `logging`)
- Use `f-strings` for string formatting
- `ruff` is the sole lint/format tool — do not use `black`, `flake8`, or `isort`
- `mypy` strict mode required across all `src/` code
- `pytest-asyncio` with `asyncio_mode = "auto"` in `pyproject.toml`

## Testing Approach

- All subsystem tests use fakes for hardware (no real Pi, sensors, or KSBU-N needed)
- `conftest.py` provides shared fixtures: in-memory SQLite session, `FakeSensorBus`, `FakeUPS`, `FakeKSBUNTransport`, `FakeGPIO`, `pytest-httpserver` for the KSBU-N web client, and a FastAPI `TestClient`
- Parser tests in `ksbu/test_parser.py` run against static HTML fixtures in `tests/fixtures/` — add real KSBU-N HTML captures there early
- Coverage target: ≥ 80% overall; 100% branch coverage on `alerts/rules.py` and `controls/policy.py`

## Network Layout

- Pi site/internet side: DHCP via `wlan0`, runs Tailscale
- Pi KSBU-N private side: `192.168.50.1` (Pi) ↔ `192.168.50.2` (KSBU-N), no internet exposure
- Dashboard: reachable only on local LAN or Tailscale (`http://ice-location-1:8080`)
- KSBU-N must never be directly exposed to the internet

## Development Phases

The spec defines 6 phases. Phase 1 is the current target:
1. **Phase 1** — Sensor logging, SQLite, Loguru, basic FastAPI dashboard, Tailscale access, systemd service
2. **Phase 2** — KSBU-N NAFEM/web client integration
3. **Phase 3** — Full alert system (email, SMS, MQTT)
4. **Phase 4** — UPS / safe shutdown
5. **Phase 5** — Relay outputs, digital/analog inputs
6. **Phase 6** — Reporting, maintenance tracking, offsite backup
