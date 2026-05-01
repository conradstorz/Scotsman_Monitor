# Project: Ice Machine Remote Monitor / Control Gateway

## Purpose

Build a Raspberry Pi 4 based monitoring and control gateway for a Scotsman Prodigy ice machine equipped with a KSBU-N Smart-Board.

The gateway will:

- Monitor independent temperature probes inside and around the ice maker.
- Communicate directly with the KSBU-N Smart-Board. (Note; seperate work has been done already to create a script to communicate with the KSBU-N. The script can be found here in this project folders.)
- Log detailed operating history locally.
- Provide private remote access through Tailscale.
- Issue alerts through multiple channels.
- Preserve raw diagnostic captures for troubleshooting.
- Provide a local and remote dashboard.
- Support future expansion for relay outputs, voltage monitoring, current monitoring, water pressure monitoring, flow sensing, and other service inputs.

The system should be treated as an edge-monitoring appliance installed near the ice machine. It should continue collecting independent environmental data even if the KSBU-N becomes unavailable.

The core design rule is:

> Independent sensors are the truth for environmental conditions.  
> The KSBU-N is the truth for machine controller state.  
> The Raspberry Pi is the historian, alert manager, dashboard, and remote access bridge.

---

## High-Level System Definition

The system consists of:

1. A Raspberry Pi 4 installed near the ice maker.
2. A private Ethernet link between the Pi and the KSBU-N Smart-Board.
3. A second network path from the Pi to the internet/site network.
4. Tailscale for private remote access.
5. One-Wire DS18B20 Dallas temperature sensors installed at multiple useful points.
6. A UPS HAT or small battery backup module for graceful shutdown and outage reporting.
7. Local SQLite storage for detailed history.
8. Detailed Loguru-based application logging.
9. A FastAPI-based local dashboard.
10. Alert integrations for email, SMS, MQTT/Home Assistant, dashboard, and future webhooks.
11. Future expansion support for relay outputs and analog/digital monitoring inputs.

---

## System Architecture

```text
Remote User / Technician
   |
   | Tailscale private encrypted network
   |
Raspberry Pi 4 Gateway
   |
   |-- Internet / site network interface
   |     - Wi-Fi or Ethernet
   |     - Provides outbound internet access
   |     - Runs Tailscale
   |
   |-- Private KSBU-N Ethernet interface
   |     - Static private subnet
   |     - No internet exposure
   |     - Direct connection to Smart-Board
   |
   |-- One-Wire sensor bus
   |     - DS18B20 waterproof temperature probes
   |
   |-- UPS / battery module
   |     - Power-loss detection
   |     - Runtime estimate
   |     - Safe shutdown
   |
   |-- Future expansion I/O
         - Relay outputs
         - Digital inputs
         - Analog sensor inputs
         - Pressure/current/voltage monitoring

KSBU-N Smart-Board
   |
Scotsman Prodigy Ice Machine
```

---

## Network Architecture

### Design Goal

The KSBU-N should never be directly exposed to the public internet.

Remote access should happen through Tailscale only.

```text
Laptop / Phone
   |
   | Tailscale
   |
Raspberry Pi
   |
   | Private subnet
   |
KSBU-N
```

### Recommended Interface Layout

The Raspberry Pi should have two logical network sides.

#### Site / Internet Side

This may be Wi-Fi or Ethernet, depending on what is easiest at the install site.

Example:

```text
Interface: wlan0
Address: DHCP from site router
Purpose:
  - Internet access
  - Tailscale connection
  - Optional MQTT/cloud/offsite backup
```

#### KSBU-N Private Side

This should be a private wired subnet. A USB Ethernet adapter may be used if the Pi's built-in Ethernet is already used for site networking.

Example:

```text
Interface: eth0 or usb0
Pi address: 192.168.50.1
KSBU-N address: 192.168.50.2
Subnet: 255.255.255.0
Gateway: none required for KSBU-N side
```

### Tailscale Access

The Pi should be reachable over Tailscale using a stable MagicDNS name, such as:

```text
ice-location-1
ice-location-1.tailnet-name.ts.net
```

The dashboard should be reachable only over local LAN or Tailscale.

Example:

```text
http://ice-location-1:8080
```

If HTTPS is desired later, use a local reverse proxy such as Caddy, but the initial system can remain HTTP-only inside Tailscale.

---

## KSBU-N Communication Strategy

### Goal

The Pi should collect machine-controller information directly from the KSBU-N.

The system should prefer a proper protocol if practical, but fall back to web interface interaction if required.

### Strategy Order

```text
1. Attempt to identify whether NAFEM protocol access is practical.
2. If practical, implement a KSBU-N NAFEM client.
3. If NAFEM access is unavailable, undocumented, or too limited, use web interface polling.
4. Preserve raw captures so the parser can be improved over time.
5. Maintain independent sensor logging regardless of KSBU-N communication status.
```

### Preferred Path: NAFEM Protocol

The KSBU-N is described by Scotsman documentation as NAFEM protocol compliant. If usable documentation, examples, or a discoverable endpoint can be found, this should be the preferred data path.

Potential benefits:

- More stable than HTML scraping.
- More machine-readable.
- Easier to poll.
- Better long-term reliability.
- Possible access to structured diagnostics.

Unknowns to resolve during implementation:

- Transport protocol.
- Port number.
- Authentication requirements.
- Data model.
- Command support.
- Whether the KSBU-N exposes enough information through NAFEM for this project.

### Fallback Path: Web Interface Polling

If NAFEM is not practical, the Pi should interact with the KSBU-N browser interface.

The web interaction client should:

- Log in if authentication is required.
- Fetch selected status/configuration pages.
- Parse current status values.
- Store parsed data.
- Save raw HTML snapshots when changed or on schedule.
- Detect authentication failures.
- Detect layout/parser failures.
- Avoid sending control commands unless explicitly enabled.

### Possible KSBU-N Data Points

The system should be designed to store values such as:

- Machine operating state.
- Freeze cycle status.
- Harvest cycle status.
- Bin full status.
- Diagnostic codes.
- Warning codes.
- Compressor runtime.
- Freeze cycle count.
- Harvest cycle count.
- Water temperature.
- Discharge temperature.
- Sump temperature if available.
- Transformer/control voltage if available.
- Water quality or water condition indicators if available.
- Cleaning/descale reminders.
- Time-to-clean setting.
- Flush level setting.
- Bin level scheduling if installed.
- Vari-Smart bin level information if installed.
- Keypad lock status.
- Controller snapshot information.
- Board/controller configuration values.

### Raw Capture Requirement

For troubleshooting, the system should optionally save raw KSBU-N responses.

Suggested policy:

```text
Save raw KSBU-N capture:
  - At startup.
  - Whenever the parsed status changes materially.
  - Whenever a fault or warning appears.
  - Every 5 to 15 minutes during normal operation.
  - Whenever parser errors occur.
```

Raw captures should be timestamped and stored in:

```text
data/raw_ksbu/
```

Example filename:

```text
2026-04-27T14-30-00_ksbu_snapshot.html
2026-04-27T14-30-00_ksbu_snapshot.json
```

### Parser Test Fixtures

Representative KSBU-N HTML and JSON responses should be captured early and saved as static test fixtures:

```text
tests/fixtures/ksbu_status_sample.html    # normal operating state
tests/fixtures/ksbu_status_fault.html     # active fault code present
tests/fixtures/ksbu_status_bin_full.html  # bin full state
tests/fixtures/ksbu_status_harvest.html   # during harvest cycle
```

These fixtures allow the parser to be tested without a live KSBU-N. The parser should be a pure function of input text → structured data, with no network or I/O dependencies, so it is trivially unit-testable against these files.



### Required Core Hardware

| Item | Purpose | Notes |
|---|---|---|
| Raspberry Pi 4 | Main gateway computer | Prefer 2GB RAM or greater |
| Raspberry Pi power supply or DIN-rail 5V supply | Stable power | Avoid cheap phone chargers |
| USB SSD or industrial microSD | Local OS/data storage | USB SSD preferred for log/database endurance |
| UPS HAT or small battery module | Graceful shutdown and power-loss reporting | Must expose battery/power status to software |
| DS18B20 waterproof temperature probes, 9+ | Temperature monitoring | Stainless probe style preferred |
| 4.7kΩ resistor | One-Wire pull-up | Between data and 3.3V |
| Ethernet cable | Pi to KSBU-N private link | Use short, serviceable cable |
| USB Ethernet adapter | Optional second Ethernet interface | Needed if built-in Ethernet is used for site network |
| Enclosure | Protect Pi and terminals | Prefer serviceable electrical enclosure |
| Terminal blocks or Wago connectors | Sensor/service wiring | Avoid permanent splices |
| Cable glands / strain relief | Wiring protection | Especially near machine vibration/moisture |
| Labels / heat shrink markers | Service identification | Label every probe and cable |

### Strongly Recommended Hardware

| Item | Purpose |
|---|---|
| USB SSD boot drive | Reduces failure risk from heavy logging |
| RTC module | Keeps time during offline boot/outage |
| DIN-rail power supply | More professional power installation |
| Inline fuse | Protect low-voltage supply |
| Ferrules and proper terminal tooling | Better field reliability |
| Small status LED or buzzer | Optional local status indication |
| Industrial enclosure with clear cover | Easier service inspection |

### Future Expansion Hardware

| Item | Purpose |
|---|---|
| Opto-isolated relay board | Future control outputs |
| Solid-state relay module | Quiet/fast switching where appropriate |
| Opto-isolated digital input board | Door switches, alarm contacts, voltage-present signals |
| ADS1115 ADC module | Analog inputs |
| 4–20 mA input module | Water pressure transducers |
| Current transformer module | Compressor/pump current monitoring |
| Voltage sensing module | Detect line/control voltage presence |
| Water pressure transducer | Future water supply monitoring |
| Flow meter | Future water flow tracking |
| Modbus RTU adapter | Future industrial sensors |
| I2C isolator | Optional protection for external I2C devices |

---

## Software Bill of Materials

### Base Operating System

| Component | Purpose |
|---|---|
| Raspberry Pi OS Lite 64-bit | Base operating system |
| systemd | Service management |
| journald | System log collection |
| logrotate | Log retention and rotation |
| chrony or systemd-timesyncd | Time synchronization |
| openssh-server | Local maintenance access |
| tailscale | Private remote access |
| ufw or nftables | Local firewall |
| git | Source/version management |
| sqlite3 CLI | Manual database inspection |
| i2c-tools | Future I2C diagnostics |
| raspi-config | Pi hardware configuration |

### Python Runtime and Packaging

| Component | Purpose |
|---|---|
| Python 3.11+ or 3.12+ | Main runtime |
| uv | Dependency management and execution |
| pyproject.toml | Project/dependency definition |
| ruff | Linting/format checks |
| pytest | Testing |
| pytest-asyncio | Async test support |
| pytest-cov | Test coverage measurement and reporting |
| pytest-httpserver | Fake HTTP server for KSBU-N integration tests |
| factory-boy | Test data factories for sensor readings, alerts, KSBU status |
| respx | HTTPX request mocking for KSBU-N unit tests |
| mypy or pyright | Type checking (treat as required, not optional) |

### Python Application Dependencies

| Component | Purpose |
|---|---|
| FastAPI | Web API/dashboard |
| Uvicorn | ASGI server |
| Pydantic v2 | Configuration and data models |
| pydantic-settings | Environment-aware settings |
| Loguru | Detailed logging |
| SQLite | Local storage engine |
| SQLAlchemy or SQLModel | Database access layer |
| Alembic | Optional database migrations |
| httpx | HTTP client for KSBU-N |
| BeautifulSoup4 | HTML parsing fallback |
| lxml | Faster/more robust HTML parsing |
| tenacity | Retry/backoff handling |
| paho-mqtt | MQTT/Home Assistant integration |
| psutil | Pi CPU/memory/disk/network health |
| gpiozero or lgpio | GPIO access |
| w1thermsensor or direct sysfs reader | DS18B20 access |
| python-dotenv | Local environment variables |
| orjson | Fast JSON serialization |
| apscheduler or native asyncio tasks | Periodic jobs |
| jinja2 | Dashboard templates |
| python-multipart | FastAPI form handling if needed |

### Optional / Future Software

| Component | Purpose |
|---|---|
| prometheus-client | Metrics endpoint |
| Grafana Alloy or agent | Future metrics forwarding |
| rclone | Offsite backup |
| smbus2 | I2C support |
| adafruit-circuitpython-ads1x15 | ADS1115 support |
| pymodbus | Modbus sensors/devices |
| apprise | Multi-channel notifications |
| Docker or Podman | Optional containerized deployment |
| Caddy | Optional reverse proxy / HTTPS |
| watchdog | File or hardware event monitoring |

---

## Sensor System

### DS18B20 One-Wire Bus

The initial system should support at least 9 DS18B20 Dallas temperature sensors.

The code should not assume exactly 9 sensors. It should support any number of configured sensors.
Likely temperatures are; Exhaust Air, Compressor Body, Compressor Hi Side and Lo side, Condensor Hi and Lo sides, Water Bath, Purge Water (to detect failed purge valve), Incoming Air, (Some ice makers have 2 ice forming evaporators and each will have;) Evap Hi and Lo sides and Hot gas valve.


### Suggested Probe Placement

| Probe | Location | Purpose |
|---|---|---|
| T1 | Bin upper air | Detect stored ice/bin air temperature |
| T2 | Bin lower air | Compare lower storage temperature |
| T3 | Evaporator area | Freeze/harvest behavior clue |
| T4 | Condenser air intake | Detect hot room / restricted intake |
| T5 | Condenser exhaust | Heat rejection trend |
| T6 | Machine ambient room | Baseline environment |
| T7 | Water inlet line | Incoming water condition |
| T8 | Sump/reservoir external area | Compare against machine-reported water/sump behavior |
| T9 | Control compartment | Electronics/enclosure heat |
| T10+ | Spare / service probe | Temporary diagnostic placement |

### Sensor Identity

Each DS18B20 has a ROM ID. The system must map ROM IDs to logical names.

Example:

```json
{
  "temperature_sensors": [
    {
      "id": "28-00000abc1234",
      "name": "bin_upper_air",
      "location": "Ice bin upper air",
      "enabled": true,
      "alert_min_f": 25,
      "alert_max_f": 45
    },
    {
      "id": "28-00000def5678",
      "name": "condenser_intake",
      "location": "Condenser intake air",
      "enabled": true,
      "alert_min_f": 35,
      "alert_max_f": 100
    }
  ]
}
```

### Sensor Failure Handling

The system should detect:

- Missing sensor.
- New unconfigured sensor.
- Sensor reading impossible value.
- Repeated read failures.
- Bus failure.
- Sudden jump outside plausible range.

Sensor issues should generate alerts and logs but should not stop the rest of the gateway.

---

## UPS / Battery / Power-Loss Handling

### Purpose

The Pi should have a small battery backup to:

- Detect site power loss.
- Send an outage alert.
- Continue logging briefly.
- Shut down cleanly before battery exhaustion.
- Record the outage and recovery event.

### Required UPS Functions

The selected UPS HAT/module should provide software-readable status:

- External power present.
- Battery mode active.
- Battery voltage or percentage.
- Estimated runtime if available.
- Low battery event.
- Shutdown signal or API.

### Power-Loss Sequence

```text
1. Detect loss of external power.
2. Log power-loss event.
3. Send urgent alert.
4. Continue monitoring if battery allows.
5. If power returns, log recovery and send recovery alert.
6. If battery gets low or outage exceeds configured runtime:
   - Send final shutdown alert.
   - Flush database/logs.
   - Shut down Pi safely.
```

### Recovery Sequence

On boot after outage:

```text
1. Detect previous unclean/clean shutdown state.
2. Log startup event.
3. Check database integrity.
4. Check KSBU-N connectivity.
5. Check sensors.
6. Send recovery summary alert.
```

---

## Data Logging Requirements

### Logging Philosophy

The system should log in enough detail that a technician can reconstruct what happened later without being on site.

There should be three types of retained information:

1. Human-readable application logs.
2. Structured database records.
3. Raw KSBU-N captures.

### Loguru Application Logs

Suggested log files:

```text
logs/ice_gateway.log
logs/sensors.log
logs/ksbu.log
logs/alerts.log
logs/control.log
logs/power.log
logs/network.log
```

Log rotation policy:

```text
- Rotate daily or at size threshold.
- Compress old logs.
- Retain at least 365 days if storage allows.
- Always keep recent logs uncompressed for service convenience.
```

### SQLite Database

Suggested database path:

```text
data/ice_gateway.sqlite
```

Suggested major tables:

| Table | Purpose |
|---|---|
| sensor_readings | Temperature readings |
| sensor_status | Sensor presence/failure state |
| ksbu_status | Parsed KSBU-N machine state |
| ksbu_faults | Fault/warning history |
| raw_capture_index | Metadata for raw KSBU captures |
| alerts | Alert lifecycle |
| power_events | Outage/battery/shutdown events |
| pi_health | CPU/memory/disk/temp health |
| network_status | Tailscale/site/KSBU connectivity |
| control_events | Future relay/control actions |
| maintenance_events | Cleaning/service history |
| config_changes | Audit trail of config edits |

### Suggested Data Frequency and Retention

| Data Type | Frequency | Retention |
|---|---:|---:|
| Temperature readings | 10–30 seconds | 1+ year |
| KSBU-N status | 30–60 seconds | 1+ year |
| KSBU-N raw snapshots | 5–15 minutes or on change | 30–90 days |
| Alerts/events | On event/change | Permanent |
| Pi health | 60 seconds | 1 year |
| Network status | 60 seconds | 1 year |
| UPS/power status | 10–30 seconds | 1 year |
| Control events | On event | Permanent |
| Maintenance events | On event | Permanent |

### Raw Capture Retention

Raw captures may consume more space than structured logs. Retention should be configurable.

Example:

```json
{
  "raw_capture": {
    "enabled": true,
    "save_on_change": true,
    "save_on_fault": true,
    "periodic_interval_minutes": 15,
    "retention_days": 60
  }
}
```

---

## Alerts and Notifications

### Alert Philosophy

Alerts should be useful, not noisy.

The system should support:

- Active alerts.
- Resolved alerts.
- Alert deduplication.
- Escalation.
- Cooldown periods.
- Severity levels.
- A full alert history.

### Alert Channels

| Channel | Purpose |
|---|---|
| Email | Detailed alerts and daily summaries |
| SMS | Urgent short messages |
| MQTT/Home Assistant | Dashboard/automation integration |
| Local dashboard | Current status and history |
| Webhook | Future integrations |
| Log file | Permanent audit trail |

### Alert Severity Levels

| Severity | Meaning |
|---|---|
| INFO | Useful status, no action needed |
| WARNING | Abnormal condition, watch closely |
| ERROR | Maintenance likely needed |
| CRITICAL | Immediate attention needed |

### Initial Alert Types

| Alert | Trigger |
|---|---|
| Pi offline | External heartbeat/tailscale check missing |
| KSBU-N unreachable | Failed polling for configured threshold |
| KSBU-N fault | Machine reports fault/warning |
| Long freeze cycle | Cycle exceeds learned/configured limit |
| Long harvest cycle | Harvest exceeds learned/configured limit |
| Bin too warm | Bin probe above threshold |
| Condenser intake too hot | Intake probe above threshold |
| Condenser delta abnormal | Exhaust/intake relationship abnormal |
| Sensor missing | Configured DS18B20 disappears |
| New sensor found | Unconfigured DS18B20 appears |
| Power failure | UPS on battery |
| Low battery | UPS low threshold reached |
| Safe shutdown pending | Battery/runtime threshold reached |
| Tailscale disconnected | Private remote access lost |
| Internet unavailable | Site connection lost |
| Disk nearly full | Logging/database risk |
| CPU temperature high | Pi thermal issue |
| Maintenance due | Cleaning/descale interval reached |
| Control output changed | Future relay/control action taken |

### Alert Deduplication

The deduplication key is the combination of `(category, source, severity)`.

A new alert is created only when no active alert with the same key exists. While the same condition persists, the existing record is updated (incrementing `notification_count` and `updated_at`). A distinct new alert is created when the condition clears and then re-triggers.

Example logic:

```text
If the same alert remains active:
  - Do not send repeated SMS every cycle.
  - Update the existing active alert record.
  - Send reminders only after configured interval.

If the alert clears:
  - Mark it resolved.
  - Send optional recovery notification.
```

---

## MQTT / Home Assistant Integration

### Purpose

MQTT support should allow Home Assistant or another dashboard to observe the system.

### MQTT Topics

Example topic structure:

```text
ice_gateway/location_1/status
ice_gateway/location_1/temperatures/bin_upper_air
ice_gateway/location_1/ksbu/state
ice_gateway/location_1/ksbu/faults
ice_gateway/location_1/power/status
ice_gateway/location_1/network/tailscale
ice_gateway/location_1/alerts/active
```

### Future Home Assistant Discovery

The system may later support Home Assistant MQTT discovery so entities appear automatically.

---

## Dashboard

### Dashboard Technology

The dashboard should be built using FastAPI and Jinja2/HTMX or a simple API-first design.

Initial preference:

```text
FastAPI + Jinja2 + simple templates
```

HTMX can be added if dynamic live refresh becomes useful.

### Access

Dashboard access should be available:

- Locally on the Pi.
- Over the site LAN if allowed.
- Over Tailscale.

No public exposure.

### Dashboard Pages

| Page | Purpose |
|---|---|
| Overview | Machine status summary |
| Temperatures | Live sensor readings and status |
| KSBU-N | Parsed Smart-Board data |
| Alerts | Active/resolved alerts |
| Trends | Temperature and cycle charts |
| Power | UPS and outage history |
| Network | Tailscale, internet, KSBU private subnet |
| Pi Health | CPU, memory, disk, temperature |
| Config | Sensor names, thresholds, alert settings |
| Maintenance | Cleaning/descale/service log |
| Raw Data | KSBU-N raw captures and parser status |
| Control | Future relay/control page, disabled by default |

### Overview Page Should Show

- Overall health: OK / Warning / Fault / Critical.
- KSBU-N reachable status.
- Machine state.
- Active faults/warnings.
- Bin temperature.
- Ambient temperature.
- Condenser intake/exhaust temperature.
- Power status.
- Last successful poll time.
- Last alert.
- Tailscale status.
- Disk space.

---

## Control Features

### Phase 1: Monitoring Only

Initial implementation should not control machine circuits.

Allowed actions:

- Read sensors.
- Read KSBU-N.
- Log data.
- Send alerts.
- Restart software service.
- Reboot Pi.
- Shut down Pi safely.
- Export diagnostics.

### Phase 2: Relay Output Support

Relay support should be built as an abstraction but disabled by policy until explicitly enabled.

Possible future outputs:

| Relay | Possible Use |
|---|---|
| R1 | Remote alarm output |
| R2 | Auxiliary fan |
| R3 | Service light |
| R4 | Water solenoid / external circuit |
| R5 | Remote reset if supported safely |
| R6 | Future machine-safe function |
| R7/R8 | Spare |

### Control Safety Rules

Any control action must require:

- Explicit config enable.
- Dashboard/admin permission.
- Confirmation for remote actions.
- Audit log entry.
- Failsafe default state.
- Clear labeling.
- Local manual override where appropriate.
- No direct compressor power interruption by default.

Important design rule:

> The Pi should not directly interrupt compressor or high-current machine power.  
> Any future control should use approved low-voltage control paths, external interposing relays, or manufacturer-supported functions.

### Future Input Monitoring

Future inputs may include:

| Input | Purpose |
|---|---|
| Door switch | Cabinet/service access detection |
| Bin switch | Independent bin status |
| Water pressure | Supply issue detection |
| Line voltage presence | Power monitoring |
| Compressor current | Compressor runtime/health |
| Pump current | Pump operation verification |
| Fan current | Condenser fan operation |
| Leak detector | Water leak alert |
| Float switch | Water level issue |
| Flow meter | Water usage/fill behavior |

---

## Configuration Design

### Philosophy

Everything should be config-driven.

The software should not require code changes for:

- Sensor names.
- Sensor thresholds.
- Poll intervals.
- KSBU-N IP/credentials.
- Alert channels.
- MQTT topics.
- Retention periods.
- Relay definitions.
- Site/machine identity.

### Configuration File Format

The project uses **TOML** as the primary configuration format (consistent with the existing `config/ksbun_gateway.toml` file and `pyproject.toml`).

The example configuration below uses JSON for readability, but the actual implementation should use TOML. The `pydantic-settings` integration should load from the TOML file and support environment-variable overrides for any field, with secrets always coming from the `.env` file or environment variables — never from the TOML config.

Validation of the loaded configuration should be tested in `test_config.py` using known-good and known-bad TOML inputs.

### Example Configuration

```json
{
  "site": {
    "name": "Location 1",
    "machine_name": "Scotsman Prodigy",
    "timezone": "America/Kentucky/Louisville"
  },
  "network": {
    "ksbu_private_interface": "eth0",
    "ksbu_gateway_ip": "192.168.50.1",
    "ksbu_ip": "192.168.50.2"
  },
  "ksbu": {
    "enabled": true,
    "host": "192.168.50.2",
    "preferred_protocol": "nafem",
    "fallback_protocol": "web",
    "username": "observer",
    "password_env": "KSBU_PASSWORD",
    "poll_interval_seconds": 60,
    "raw_capture_enabled": true
  },
  "tailscale": {
    "required": true,
    "hostname": "ice-location-1"
  },
  "temperature_sensors": [
    {
      "id": "28-00000abc1234",
      "name": "bin_upper_air",
      "location": "Ice bin upper air",
      "enabled": true,
      "alert_min_f": 25,
      "alert_max_f": 45
    }
  ],
  "logging": {
    "level": "DEBUG",
    "retain_days": 365,
    "raw_ksbu_snapshots": true
  },
  "alerts": {
    "email_enabled": true,
    "sms_enabled": true,
    "mqtt_enabled": true,
    "webhook_enabled": false
  },
  "backup": {
    "enabled": false,
    "provider": "stub",
    "interval_hours": 24
  },
  "controls": {
    "relay_outputs_enabled": false,
    "remote_control_enabled": false
  }
}
```

### Secrets

Secrets should not be stored directly in the main config file.

Use:

```text
.env
systemd EnvironmentFile
```

Example:

```text
KSBU_PASSWORD=change-me
SMTP_PASSWORD=change-me
TWILIO_AUTH_TOKEN=change-me
MQTT_PASSWORD=change-me
```

---

## Project Directory Structure

Suggested repo layout:

```text
ice_gateway/
  pyproject.toml
  README.md
  SPEC.md
  config/
    config.example.json
    config.local.json
  data/
    ice_gateway.sqlite
    raw_ksbu/
  logs/
  scripts/
    install_service.sh
    collect_diagnostics.sh
  systemd/
    ice-gateway.service
  tests/
    conftest.py                        # shared fixtures: in-memory DB, fake config, fake hardware drivers
    factories.py                       # test data factories for sensor readings, alerts, KSBU status
    fixtures/
      ksbu_status_sample.html          # representative KSBU-N web page for parser tests
      ksbu_status_fault.html           # fault-state page for alert trigger tests
      ksbu_status_unreachable.txt      # notes for simulating KSBU-N timeout
    test_config.py
    test_models.py

    sensors/
      test_onewire.py                  # sensor bus polling, missing/new sensor detection
      test_sensor_failure_modes.py     # impossible values, repeated failures, bus failure
      test_pi_health.py
      test_ups.py                      # power loss sequence, low-battery shutdown trigger

    ksbu/
      test_nafem_client.py             # NAFEM request/response cycle, auth failure, retry
      test_web_client.py               # login flow, page parsing, session expiry
      test_parser.py                   # parse known HTML/JSON → structured status
      test_snapshots.py                # raw capture save logic, retention cleanup

    alerts/
      test_alert_manager.py            # deduplication, cooldown, escalation, resolution
      test_alert_rules.py              # each alert type fires at right threshold
      test_email.py
      test_sms.py
      test_mqtt.py

    dashboard/
      test_routes.py                   # FastAPI TestClient, each page returns 200
      test_overview.py                 # correct health state rendered

    tasks/
      test_polling.py                  # isolated subsystem failure does not stop loop
      test_retention.py                # old records deleted on schedule

    database/
      test_writes.py                   # each model round-trips through SQLite
      test_integrity.py                # startup integrity check, recovery after crash

    integration/
      test_sensor_to_alert.py          # end-to-end: fake bus missing → alert fires → DB entry
      test_ksbu_to_alert.py            # fake KSBU response with fault → alert fires
      test_power_sequence.py           # fake UPS: power loss → log → alert → shutdown

  src/
    ice_gateway/
      __init__.py
      main.py
      config.py
      logging_setup.py
      models.py
      database.py
      constants.py

      sensors/
        __init__.py
        onewire.py
        pi_health.py
        ups.py

      ksbu/
        __init__.py
        base.py
        nafem_client.py
        web_client.py
        parser.py
        snapshots.py

      alerts/
        __init__.py
        manager.py
        email.py
        sms.py
        mqtt.py
        webhook.py

      controls/
        __init__.py
        relay_board.py
        policy.py
        digital_inputs.py
        analog_inputs.py

      dashboard/
        __init__.py
        app.py
        routes.py
        templates/
          base.html
          overview.html
          temperatures.html
          ksbu.html
          alerts.html
          power.html
          network.html
          config.html
        static/

      tasks/
        __init__.py
        polling.py
        backup.py
        retention.py
        heartbeat.py
```

---

## Core Polling Behavior

### Main Polling Loop

```text
Every 10 to 30 seconds:
  - Read all configured DS18B20 sensors.
  - Detect missing/new sensors.
  - Read UPS status.
  - Read Pi health.
  - Store readings.
  - Evaluate sensor and power alerts.

Every 30 to 60 seconds:
  - Poll KSBU-N.
  - Parse machine status.
  - Store parsed values.
  - Save raw snapshot if required.
  - Evaluate machine alerts.

Every 60 seconds:
  - Check network state.
  - Check Tailscale status.
  - Check KSBU private subnet reachability.
  - Store network health.

Every 5 minutes:
  - Publish MQTT summary state.
  - Send heartbeat.
  - Run lightweight database maintenance.

Every hour:
  - Summarize machine health.
  - Run retention cleanup.
  - Prepare backup package if enabled.

On alert state change:
  - Store alert event.
  - Send configured notifications.
  - Publish MQTT update.
  - Update dashboard state.

On power failure:
  - Log event.
  - Send urgent alert.
  - Continue monitoring if possible.
  - Shut down safely if needed.
```

### Failure Isolation

A failure in one subsystem should not stop the whole application.

Examples:

- KSBU-N unavailable: continue DS18B20 logging.
- MQTT unavailable: continue local logging and email/SMS.
- Email unavailable: continue SMS/MQTT/dashboard.
- One sensor missing: continue reading other sensors.
- Raw capture save failure: continue parsed logging.

---

## Data Models

### Sensor Reading

Fields:

```text
id
timestamp
sensor_id
sensor_name
temperature_c
temperature_f
read_success
error_message
ksbu_reachable_at_read
read_quality
```

`ksbu_reachable_at_read` is a boolean recording whether the KSBU-N was reachable at the time of this reading, allowing queries to flag readings taken during communication outages.

`read_quality` is an enum: `ok`, `crc_error`, `impossible_value`, `missing`, `bus_fault`.

### KSBU Status

Fields:

```text
id
timestamp
reachable
protocol_used
machine_state
freeze_cycle_active
harvest_cycle_active
bin_full
fault_code
warning_code
compressor_runtime
freeze_cycle_count
harvest_cycle_count
water_temperature
discharge_temperature
raw_capture_id
parse_success
parse_error
```

### Alert Record

Fields:

```text
id
created_at
updated_at
resolved_at
severity
category
source
message
details_json
active
notification_count
last_notification_at
```

### Power Event

Fields:

```text
id
timestamp
event_type
external_power_present
battery_percent
battery_voltage
estimated_runtime_seconds
action_taken
```

### Control Event

Fields:

```text
id
timestamp
actor
control_name
requested_state
actual_state
success
reason
safety_policy_result
```

---

## Security Requirements

### Required Security Controls

| Requirement | Reason |
|---|---|
| KSBU-N on private subnet | Prevent direct exposure of embedded device |
| Tailscale-only remote access | Encrypted private remote access |
| No public port forwarding | Avoid internet attack surface |
| Firewall enabled | Restrict local ports |
| Secrets in environment file | Avoid credentials in Git |
| Read-only dashboard role | Safe observation |
| Admin role for future controls | Protect control actions |
| Audit all actions | Service traceability |
| Keep OS updated | Security maintenance |

### Suggested Firewall Policy

Allow:

```text
SSH from local/Tailscale only
Dashboard port from Tailscale only
Outbound internet
Private KSBU-N subnet traffic
```

Deny:

```text
Public inbound dashboard access
Public inbound KSBU-N access
Unknown inbound traffic
```

### Credential Policy

- Change KSBU-N default password.
- Use a read-only or observer user where possible.
- Use a separate admin password only for setup/control functions.
- Do not store passwords in the repo.
- Do not expose KSBU-N web UI directly to the internet.

---

## Backup and Offsite Sync

### Initial Requirement

Local logging in great detail is required.

Offsite backup should be stubbed but not required for Phase 1.

### Backup Package Contents

A backup job should eventually collect:

```text
- SQLite database dump
- config.local.json
- recent logs
- alert history
- raw KSBU snapshots
- system version info
- installed package list
```

### Future Backup Targets

| Target | Use |
|---|---|
| Synology NAS | Best fit for owned infrastructure |
| SFTP | Simple remote copy |
| rclone target | Cloud/offsite backup |
| MQTT retained state | Lightweight status backup |
| Git repo | Config-only backup, no secrets |

### Backup Safety

Backups should not include:

- Plaintext secrets.
- `.env` unless explicitly encrypted.
- Full credentials.
- Tailscale auth keys.

---

## Installation / Deployment

### Intended Deployment Model

The system should run as a systemd service.

Example service name:

```text
ice-gateway.service
```

### Service Behavior

The service should:

- Start automatically on boot.
- Restart on failure.
- Write logs immediately.
- Wait for network if required.
- Continue operating if internet is down.
- Expose dashboard locally/Tailscale.
- Shut down gracefully on SIGTERM.

### Example Service Concept

```ini
[Unit]
Description=Ice Gateway Monitor
After=network-online.target tailscaled.service
Wants=network-online.target

[Service]
WorkingDirectory=/opt/ice_gateway
EnvironmentFile=/etc/ice-gateway/ice-gateway.env
ExecStart=/usr/bin/env uv run ice-gateway
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Development Phases

### Phase 1 — Foundation

Goals:

**Checkpoint 1a — Pi setup and connectivity:**
- [ ] Raspberry Pi OS install.
- [ ] uv project setup.
- [ ] Tailscale setup.
- [ ] Repeatable setup script for fresh Raspberry Pi.
- [ ] Static private KSBU subnet configured.
- [ ] DS18B20 sensor discovery working.
- [ ] Sensor config mapping.

**Checkpoint 1b — Data foundation:**
- [ ] SQLite logging.
- [ ] Loguru logging with rotation.
- [ ] In-memory DB test fixture established.
- [ ] `test_config.py` passing.
- [ ] `test_onewire.py` passing against fake sensor bus.
- [ ] `test_pi_health.py` passing.

**Checkpoint 1c — Visible system:**
- [ ] Basic FastAPI dashboard running.
- [ ] Pi health monitoring visible.
- [ ] Basic systemd service starts on boot.
- [ ] Dashboard reachable over Tailscale.

Deliverable:

```text
A working Pi that can log all temperature sensors and show them remotely over Tailscale.
```

Test deliverable:

```text
conftest.py with shared fixtures.
test_config.py, test_models.py, sensors/test_onewire.py, sensors/test_pi_health.py all passing.
Coverage ≥ 80% on sensors/ and config.py.
```

### Phase 2 — KSBU-N Integration

Goals:

- Confirm KSBU-N IP/private subnet.
- Test NAFEM access.
- Implement NAFEM client if practical.
- Implement web client fallback.
- Parse current machine status.
- Store machine data.
- Save raw snapshots.
- Alert on KSBU-N unreachable.
- Alert on machine warnings/faults.

Deliverable:

```text
The Pi can show both independent sensors and KSBU-N controller status.
```

Test deliverable:

```text
ksbu/test_parser.py passing against HTML fixtures (normal, fault, harvest states).
ksbu/test_web_client.py passing against pytest-httpserver fake.
ksbu/test_nafem_client.py passing or explicitly skipped if NAFEM not available.
ksbu/test_snapshots.py passing.
integration/test_ksbu_to_alert.py passing.
```

### Phase 3 — Alerts

Goals:

- Email alerts.
- SMS alerts. (Stub for Twillio here at first)
- MQTT/Home Assistant publishing.
- Dashboard active alert panel.
- Alert deduplication.
- Alert resolution/recovery messages.
- Alert severity levels.
- Daily/weekly summary reports.

Deliverable:

```text
The system can notify you when something matters without constant noise.
```

Test deliverable:

```text
alerts/test_alert_manager.py: deduplication, cooldown, escalation, resolution all covered.
alerts/test_alert_rules.py: every alert type fires at correct threshold.
alerts/test_email.py, test_sms.py, test_mqtt.py passing with channel mocks.
integration/test_sensor_to_alert.py passing.
```

### Phase 4 — UPS / Safe Shutdown

Goals:

- Integrate UPS module. (UPS will need to power cellular internet gateway as well as rpi)
- Detect power loss.
- Send power-loss alert.
- Track battery runtime.
- Safe shutdown on low battery.
- Recovery summary after boot.

Deliverable:

```text
The Pi survives outages cleanly and reports what happened.
```

Test deliverable:

```text
sensors/test_ups.py: full power-loss → continue → low battery → shutdown sequence.
integration/test_power_sequence.py: fake UPS driver, confirms alert firing and DB events.
```

### Phase 5 — Expansion I/O

Goals:

- Relay abstraction.
- Relay safety policy.
- Digital input abstraction.
- ADC abstraction.
- Water pressure input support.
- Current/voltage monitoring support.
- Control dashboard page, disabled by default.

Deliverable:

```text
The codebase is ready for future control/monitoring circuits without redesign.
```

Test deliverable:

```text
controls/test_safety_policy.py: every control action requires explicit enable, every
  unsafe combination is rejected, audit log entry is confirmed.
All relay and digital input tests use fake GPIO drivers — no hardware required.
```

### Phase 6 — Reporting / Maintenance

Goals:

- Maintenance log.
- Cleaning/descale tracking.
- Runtime/cycle summaries.
- Temperature trend reports.
- Freeze/harvest trend analysis.
- Offsite backup implementation.
- Export diagnostic bundle.

Deliverable:

```text
The gateway becomes a service history and predictive maintenance tool.
```

Test deliverable:

```text
tasks/test_retention.py: old records deleted, retention thresholds respected.
Backup export produces a valid archive without secrets.
Daily/weekly summary generation tested with known DB contents.
Full test suite passing with ≥ 80% coverage across all modules.
```

---

## Testing Requirements

### Design Principle: Hardware Abstraction First

The most important testing requirement is that **all hardware-touching code must sit behind a protocol or ABC**. Without this, every test that involves sensors, UPS, GPIO, or network interfaces requires physical hardware. Define these abstractions before writing any implementation:

- `SensorBusReader` — ABC for reading the One-Wire bus. Production: reads `/sys/bus/w1/devices/`. Test: `FakeSensorBus` returning scripted readings or failures.
- `UPSStatusProvider` — ABC for battery/power state. Production: reads HAT via I2C. Test: `FakeUPS` returning scripted battery percentages and power-present flags.
- `NetworkChecker` — ABC for Tailscale/internet/KSBU reachability. Test: `FakeNetworkChecker` injecting "offline" scenarios without disconnecting anything.
- `KSBUNTransport` — ABC for the KSBU-N communication layer. Both NAFEM and web clients implement this. Test: `FakeKSBUNTransport` returning fixture HTML/JSON.
- `GPIOController` — ABC for relay/digital I/O. Test: `FakeGPIO` recording state changes without hardware.

All production code must accept these dependencies via constructor injection, not import-time globals.

### Shared Test Fixtures (`conftest.py`)

Key shared fixtures that must be defined before any subsystem tests:

| Fixture | Purpose |
|---|---|
| `db_session` | In-memory SQLite session, rolled back after each test |
| `fake_sensor_bus(readings)` | Injectable fake that returns scripted readings or errors |
| `fake_ksbu_server` | `pytest-httpserver` fixture serving known KSBU-N HTML pages |
| `fake_mqtt_client` | Captures published messages for assertion |
| `app_client` | FastAPI `TestClient` with all fake dependencies injected |
| `fake_ups(state)` | Scripted UPS battery/power states |
| `alert_manager` | Alert manager instance wired to in-memory DB and fake channels |

### Unit Tests

Each test module should test one unit in isolation using fakes for all dependencies.

**`test_config.py`**
- Config loads correctly from valid TOML.
- Missing required fields raise a validation error.
- Unknown fields raise a validation error or are ignored (document which).
- Environment variable overrides work for all secret fields.

**`test_models.py`**
- Each Pydantic model accepts valid data.
- Each Pydantic model rejects invalid data with correct error fields.
- `read_quality` enum values cover all documented failure modes.

**`sensors/test_onewire.py`**
- All configured sensors return readings normally.
- Missing sensor is detected and flagged.
- New unconfigured sensor is detected and flagged.
- CRC error is classified as `read_quality = crc_error`.
- Impossible temperature value (below -50°C or above 150°C) is flagged.
- Bus failure stops bus reads but does not raise to the polling loop.
- Each failure mode produces the correct log message.

**`sensors/test_sensor_failure_modes.py`**
- Repeated failures increment a failure counter.
- Alert fires after configured failure threshold.
- Single recovery clears the failure count.

**`sensors/test_pi_health.py`**
- CPU temperature, memory, disk, and network stats are read and stored.
- High CPU temperature triggers the correct alert category.

**`sensors/test_ups.py`**
- External power present: no alert.
- Power lost: power-loss event logged, alert fires.
- Power restored: recovery event logged, recovery alert fires.
- Low battery threshold: shutdown-pending alert fires.
- Battery percentage stored correctly in power_events table.

**`ksbu/test_parser.py`**
- Parse `ksbu_status_sample.html` → expected field values (fixture-driven).
- Parse `ksbu_status_fault.html` → fault code present, parse_success True.
- Parse `ksbu_status_bin_full.html` → bin_full True.
- Parse `ksbu_status_harvest.html` → harvest_cycle_active True.
- Malformed HTML → parse_success False, parse_error populated.
- Parser is a pure function: no I/O, no network calls.

**`ksbu/test_web_client.py`**
- Login page served → client posts credentials → status page fetched.
- Session expiry detected → re-authentication attempted.
- 3 consecutive failures → unreachable flag set.
- Retry/backoff fires on 5xx responses.

**`ksbu/test_nafem_client.py`**
- Successful request/response cycle → structured data returned.
- Auth failure → logged, fallback triggered.
- Test skipped with clear skip message if NAFEM endpoint is not yet characterized.

**`ksbu/test_snapshots.py`**
- Raw HTML saved to correct path with correct filename format.
- Retention cleanup deletes files older than configured threshold.
- Save failure is logged but does not propagate.

**`alerts/test_alert_manager.py`**
- New alert condition → alert record created with `active = True`.
- Same condition re-checked → existing record updated, not duplicated (dedup key: `(category, source, severity)`).
- Condition clears → alert resolved, `resolved_at` populated.
- Same condition re-triggers after resolution → new alert record created.
- Cooldown: notification not sent again until interval expires.
- `notification_count` increments on each reminder send.

**`alerts/test_alert_rules.py`**
- Each alert type in the Initial Alert Types table is tested individually.
- Bin temperature above threshold → `BIN_TOO_WARM` alert with `ERROR` severity.
- Condenser intake above threshold → `CONDENSER_INTAKE_HOT` alert.
- Sensor missing for configured threshold → `SENSOR_MISSING` alert.
- KSBU-N unreachable for configured threshold → `KSBU_UNREACHABLE` alert.
- Disk above threshold → `DISK_NEARLY_FULL` alert.

**`alerts/test_email.py`, `test_sms.py`, `test_mqtt.py`**
- Each channel sends correctly formatted messages when given an alert record.
- Channel unavailable → exception is caught and logged, not propagated.
- MQTT publishes to the correct topic structure.

**`controls/test_safety_policy.py`**
- Relay action with `relay_outputs_enabled = False` → rejected, audit log entry.
- Relay action with `relay_outputs_enabled = True` and confirmed → accepted, audit log entry.
- `actual_state` in control event reflects actual GPIO result.

**`database/test_writes.py`**
- Each model (sensor reading, KSBU status, alert record, power event, control event) round-trips through SQLite.
- Timestamps are stored as UTC and retrieved correctly.

**`database/test_integrity.py`**
- Startup integrity check passes on a clean DB.
- Startup integrity check detects and logs corruption.

**`tasks/test_polling.py`**
- KSBU-N unavailable: sensor logging continues normally.
- MQTT unavailable: local DB write still occurs.
- One sensor missing: other sensors still read correctly.
- Exception in one subsystem does not propagate to the main polling loop.

**`tasks/test_retention.py`**
- Records older than retention threshold are deleted.
- Records within retention threshold are kept.
- Raw capture files older than configured days are deleted.

**`dashboard/test_routes.py`**
- Every defined dashboard route returns 200 with `app_client`.
- Overview page reflects current health state from injected fake data.

### Integration Tests

Integration tests wire multiple real subsystems together with only hardware fakes at the boundaries.

**`integration/test_sensor_to_alert.py`**
- Fake sensor bus returns missing sensor → polling loop detects → alert record created → DB entry confirmed.

**`integration/test_ksbu_to_alert.py`**
- Fake KSBU server returns fault HTML → parser extracts fault → alert manager creates fault alert → MQTT publish captured.

**`integration/test_power_sequence.py`**
- Fake UPS: external power present → no event.
- Power lost → power_events record created → alert fires.
- Battery drops below threshold → shutdown-pending alert fires.
- Power restored → recovery event logged → recovery alert fires.

### Field Tests (Manual Acceptance)

These are manual verification steps performed on the installed system before declaring a phase complete:

- Pull one DS18B20 sensor and verify `SENSOR_MISSING` alert fires within expected window.
- Disconnect KSBU-N Ethernet and verify `KSBU_UNREACHABLE` alert fires.
- Block internet access and verify local logging continues uninterrupted.
- Disconnect site power and verify UPS behavior, power-loss alert, and clean shutdown.
- Fill disk above threshold and verify `DISK_NEARLY_FULL` alert fires.
- Reboot Pi and verify `ice-gateway.service` starts automatically.
- Confirm dashboard is reachable over Tailscale from a remote device.

### Coverage Target

```text
Minimum: 80% line coverage across all src/ modules.
Priority: 100% branch coverage of alert_rules.py and controls/policy.py.
```

Run with:

```bash
uv run pytest --cov=src/ice_gateway --cov-report=term-missing
```

---

## Maintenance Features

### Local Maintenance Log

The dashboard should allow recording:

- Cleaning performed.
- Descale performed.
- Filter change.
- Sensor replacement.
- Water issue.
- Service call.
- Manual inspection.
- Parts replaced.
- Notes.

### Maintenance Reminder Triggers

Reminders may be based on:

- Calendar interval.
- Runtime.
- Freeze cycle count.
- KSBU-N time-to-clean values.
- Manual schedule.

---

## Reporting Features

### Daily Summary

Possible daily report content:

- Machine reachable percentage.
- Average bin temperature.
- Maximum bin temperature.
- Average ambient temperature.
- Number of faults/warnings.
- Number of cycles if available.
- Power events.
- Sensor failures.
- Disk/CPU health.

### Weekly Summary

Possible weekly report content:

- Temperature trends.
- Condenser temperature trend.
- Freeze/harvest abnormality count.
- Maintenance reminders.
- Uptime.
- Alert summary.

---

## Implementation Notes

### Python Style Preferences

The project should use:

- `uv` for dependency management and execution.
- Pydantic v2 for schemas.
- Loguru for logging.
- pathlib for paths.
- pytest for tests.
- f-strings for string formatting.
- Sphinx-style docstrings for functions.
- Existing comments should be preserved once code exists; if comments are wrong, add clarification rather than deleting them.

### Async Test Configuration

All async code uses `pytest-asyncio`. Set asyncio mode in `pyproject.toml` to avoid per-test decoration:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### Logging Preferences

Use detailed logging with messages suitable for field debugging.

Examples:

```text
INFO: Starting ice gateway service
INFO: Loaded 9 configured temperature sensors
WARNING: KSBU-N unreachable after 3 attempts
ERROR: Sensor bin_upper_air missing for 120 seconds
CRITICAL: Power failure detected, battery at 18%, shutdown pending
```

---

## Code Quality Gates

The following checks must pass before any code is considered complete. These should be run locally before commit and enforced in CI.

### Linting and Formatting

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

`ruff` is the sole formatting and lint tool. Do not use `black`, `flake8`, or `isort` separately.

### Type Checking

```bash
uv run mypy src/ice_gateway --strict --no-error-summary
```

`mypy` strict mode is required across all `src/` code. `tests/` may use `--ignore-missing-imports` for test-only packages.

### Test Suite

```bash
uv run pytest --cov=src/ice_gateway --cov-report=term-missing --cov-fail-under=80
```

Minimum 80% line coverage. 100% branch coverage required on `alerts/rules.py` and `controls/policy.py`.

### CI Pipeline Order

```text
1. ruff check
2. ruff format --check
3. mypy strict
4. pytest with coverage
```

Any failure in any step blocks merging. Steps run in order; later steps are skipped if earlier steps fail to reduce noise.

---

## Open Technical Questions

These should be resolved during implementation:

1. Can the KSBU-N NAFEM protocol be used directly?
2. What exact NAFEM transport/port/data model does the KSBU-N expose?
3. Does the KSBU-N require authentication for all useful web pages?
4. Which KSBU-N fields are available without admin access?
5. Can useful data be exported as structured values, or only HTML?
6. Which UPS HAT/module has the best Linux support?
7. What is the most reliable way to mount 9+ DS18B20 sensors in/around the machine?
8. What alert channel should be considered authoritative for urgent events?
9. How much raw KSBU-N capture history can the selected storage retain?
10. Should a second Ethernet adapter be standard in the design?

---

## Minimum Viable Product

The MVP should include:

- Raspberry Pi 4.
- Tailscale remote access.
- Private Ethernet link to KSBU-N.
- DS18B20 sensor logging.
- SQLite database.
- Loguru logs.
- Basic dashboard.
- Basic alerts.
- UPS power-loss handling stub.
- KSBU-N web polling stub.
- Config file.
- systemd service.

MVP success criteria:

```text
From a remote computer over Tailscale, the user can:
  - Open the dashboard.
  - See live temperatures.
  - See whether KSBU-N is reachable.
  - See Pi health.
  - See active alerts.
  - Confirm data is being logged locally.
```

---

## Long-Term Vision

The finished system should become a dedicated ice-machine operations gateway.

Long-term capabilities:

- Remote service visibility.
- Independent temperature verification.
- Controller status logging.
- Fault alerts.
- Power-loss reporting.
- Maintenance history.
- Trend analysis.
- Predictive service clues.
- Optional future control circuits.
- Offsite backup/reporting.
- Home Assistant integration.
- Expandable sensor/control platform for other machines.

---

## End of Specification
