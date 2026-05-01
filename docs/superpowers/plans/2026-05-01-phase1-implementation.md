# Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working Raspberry Pi gateway that logs DS18B20 temperature sensors and Pi health to SQLite and serves a live dashboard over Tailscale.

**Architecture:** A single asyncio process runs a polling loop (sensors → SQLite) alongside a Uvicorn/FastAPI server. All hardware is behind ABCs so every test runs without a real Pi, sensor bus, or network. Setup scripts provision a fresh Raspbian image into a fully configured appliance.

**Tech Stack:** Python 3.13, FastAPI, Uvicorn, SQLAlchemy 2, Pydantic v2, pydantic-settings (TOML), Loguru, psutil, pytest, ruff, mypy

---

## File Map

| File | Responsibility |
|---|---|
| `pyproject.toml` | Dependencies, entry point, pytest/ruff/mypy config |
| `.gitignore` | Exclude runtime data, secrets, venv |
| `.env.example` | Documents all secret env vars |
| `config/config.example.toml` | Documented example config committed to git |
| `config/config.local.toml` | Machine-specific config, gitignored |
| `src/ice_gateway/constants.py` | `ReadQuality` enum |
| `src/ice_gateway/models.py` | Pydantic models: `SensorConfig`, `SensorReading`, `PiHealth` |
| `src/ice_gateway/config.py` | `AppConfig` pydantic-settings class loading TOML + .env |
| `src/ice_gateway/database.py` | SQLAlchemy engine, ORM rows, `init_db`, `get_session` |
| `src/ice_gateway/logging_setup.py` | Loguru sinks with rotation |
| `src/ice_gateway/sensors/base.py` | `SensorBusReader` ABC |
| `src/ice_gateway/sensors/onewire.py` | Production DS18B20 reader via sysfs |
| `src/ice_gateway/sensors/pi_health.py` | psutil CPU/memory/disk/temperature |
| `src/ice_gateway/dashboard/app.py` | FastAPI app factory |
| `src/ice_gateway/dashboard/routes.py` | Route handlers returning HTML + JSON |
| `src/ice_gateway/dashboard/templates/base.html` | Shared layout |
| `src/ice_gateway/dashboard/templates/overview.html` | Sensor + health summary |
| `src/ice_gateway/dashboard/static/style.css` | Minimal styling |
| `src/ice_gateway/tasks/polling.py` | Asyncio polling loop |
| `src/ice_gateway/main.py` | Entry point: wires and starts everything |
| `systemd/ice-gateway.service` | systemd unit |
| `scripts/00_README.sh` | Prints install order, verifies files present |
| `scripts/01_setup_os.sh` | apt update/upgrade, base packages |
| `scripts/02_setup_network.sh` | Static IP on eth0, UFW firewall |
| `scripts/03_setup_tailscale.sh` | Install Tailscale, prompt auth key |
| `scripts/04_setup_onewire.sh` | Enable 1-wire overlay in /boot/firmware/config.txt |
| `scripts/05_setup_python.sh` | Install uv, uv sync |
| `scripts/06_deploy_app.sh` | Copy app, install + start systemd service |
| `tests/conftest.py` | Shared fixtures: `db_engine`, `db_session`, `fake_sensor_bus`, `app_client` |
| `tests/fixtures/config_valid.toml` | Known-good config for test_config.py |
| `tests/fixtures/config_missing_sensor_id.toml` | Known-bad config: sensor missing required `id` |
| `tests/test_config.py` | AppConfig loads valid TOML, rejects invalid |
| `tests/test_models.py` | Pydantic model validation |
| `tests/test_database.py` | ORM round-trips through in-memory SQLite |
| `tests/sensors/test_onewire.py` | Normal read, missing sensor, CRC error, bus fault, impossible value |
| `tests/sensors/test_pi_health.py` | Health stats read and stored |
| `tests/dashboard/test_routes.py` | Every route returns 200 |

---

## Task 1: Project Scaffolding

**Files:**
- Modify: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/ice_gateway/__init__.py`
- Create: `src/ice_gateway/sensors/__init__.py`
- Create: `src/ice_gateway/dashboard/__init__.py`
- Create: `src/ice_gateway/tasks/__init__.py`
- Create: `data/.gitkeep`
- Create: `logs/.gitkeep`

- [ ] **Step 1: Replace pyproject.toml with the full project configuration**

```toml
[project]
name = "scotsman-monitor"
version = "0.1.0"
description = "Raspberry Pi monitoring gateway for Scotsman Prodigy ice machine"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.0",
    "pydantic-settings[toml]>=2.3",
    "loguru>=0.7.3",
    "sqlalchemy>=2.0",
    "psutil>=6.0",
    "jinja2>=3.1",
    "requests>=2.33.1",
]

[project.scripts]
ice-gateway = "ice_gateway.main:main"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "httpx>=0.28",
    "ruff>=0.8",
    "mypy>=1.13",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/ice_gateway"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.mypy]
python_version = "3.13"
strict = true
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
.venv/
*.egg-info/
dist/
build/
.mypy_cache/
.ruff_cache/
.pytest_cache/

# Project runtime — keep directory, ignore contents
data/*.sqlite
data/raw_ksbu/
logs/*.log
logs/*.gz

# Machine config and secrets
config/config.local.toml
.env

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 3: Create the package `__init__.py` files and runtime directories**

Create these files, all empty:
- `src/ice_gateway/__init__.py`
- `src/ice_gateway/sensors/__init__.py`
- `src/ice_gateway/dashboard/__init__.py`
- `src/ice_gateway/tasks/__init__.py`
- `data/.gitkeep`
- `logs/.gitkeep`

Also create empty placeholder files for test subdirectories (no `__init__.py` needed for pytest):
- `tests/sensors/` (directory only, create a `.gitkeep`)
- `tests/dashboard/` (directory only, create a `.gitkeep`)
- `tests/fixtures/` (directory only, create a `.gitkeep`)

- [ ] **Step 4: Install dependencies**

```bash
uv sync
```

Expected: dependencies install without error, `.venv` is created.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore src/ data/ logs/ tests/
git commit -m "feat: project scaffolding — dirs, deps, entry point config"
```

---

## Task 2: Constants

**Files:**
- Create: `src/ice_gateway/constants.py`

- [ ] **Step 1: Write `src/ice_gateway/constants.py`**

```python
from enum import Enum


class ReadQuality(str, Enum):
    OK = "ok"
    CRC_ERROR = "crc_error"
    IMPOSSIBLE_VALUE = "impossible_value"
    MISSING = "missing"
    BUS_FAULT = "bus_fault"
```

- [ ] **Step 2: Verify import works**

```bash
uv run python -c "from ice_gateway.constants import ReadQuality; print(list(ReadQuality))"
```

Expected: `[<ReadQuality.OK: 'ok'>, <ReadQuality.CRC_ERROR: 'crc_error'>, ...]`

- [ ] **Step 3: Commit**

```bash
git add src/ice_gateway/constants.py
git commit -m "feat: ReadQuality enum"
```

---

## Task 3: Pydantic Models

**Files:**
- Create: `src/ice_gateway/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing tests in `tests/test_models.py`**

```python
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from ice_gateway.models import SensorConfig, SensorReading, PiHealth
from ice_gateway.constants import ReadQuality


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TestSensorConfig:
    def test_valid(self):
        s = SensorConfig(id="28-abc123", name="bin_upper_air", location="Bin upper air")
        assert s.id == "28-abc123"
        assert s.enabled is True
        assert s.alert_min_f is None

    def test_with_thresholds(self):
        s = SensorConfig(
            id="28-abc123",
            name="bin_upper_air",
            location="Bin",
            alert_min_f=25.0,
            alert_max_f=45.0,
        )
        assert s.alert_min_f == 25.0

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            SensorConfig(name="bin_upper_air", location="Bin")  # type: ignore[call-arg]

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            SensorConfig(id="28-abc123", location="Bin")  # type: ignore[call-arg]


class TestSensorReading:
    def test_valid_ok(self):
        r = SensorReading(
            sensor_id="28-abc123",
            sensor_name="bin_upper_air",
            temperature_c=2.5,
            temperature_f=36.5,
            read_quality=ReadQuality.OK,
            timestamp=_now(),
        )
        assert r.read_quality == ReadQuality.OK
        assert r.error_message is None

    def test_valid_missing(self):
        r = SensorReading(
            sensor_id="28-abc123",
            sensor_name="bin_upper_air",
            temperature_c=None,
            temperature_f=None,
            read_quality=ReadQuality.MISSING,
            error_message="Device file not found",
            timestamp=_now(),
        )
        assert r.temperature_c is None

    def test_invalid_quality_raises(self):
        with pytest.raises(ValidationError):
            SensorReading(
                sensor_id="28-abc123",
                sensor_name="bin_upper_air",
                temperature_c=None,
                temperature_f=None,
                read_quality="not_a_quality",  # type: ignore[arg-type]
                timestamp=_now(),
            )


class TestPiHealth:
    def test_valid(self):
        h = PiHealth(
            cpu_temp_c=52.3,
            cpu_percent=12.5,
            memory_percent=44.0,
            disk_percent=18.0,
            timestamp=_now(),
        )
        assert h.cpu_temp_c == 52.3

    def test_cpu_temp_optional(self):
        h = PiHealth(
            cpu_temp_c=None,
            cpu_percent=12.5,
            memory_percent=44.0,
            disk_percent=18.0,
            timestamp=_now(),
        )
        assert h.cpu_temp_c is None
```

- [ ] **Step 2: Run tests and confirm they fail**

```bash
uv run pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'ice_gateway.models'`

- [ ] **Step 3: Write `src/ice_gateway/models.py`**

```python
from datetime import datetime
from pydantic import BaseModel
from .constants import ReadQuality


class SensorConfig(BaseModel):
    id: str
    name: str
    location: str
    enabled: bool = True
    alert_min_f: float | None = None
    alert_max_f: float | None = None


class SensorReading(BaseModel):
    sensor_id: str
    sensor_name: str
    temperature_c: float | None
    temperature_f: float | None
    read_quality: ReadQuality
    error_message: str | None = None
    timestamp: datetime


class PiHealth(BaseModel):
    cpu_temp_c: float | None
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    timestamp: datetime
```

- [ ] **Step 4: Run tests and confirm they pass**

```bash
uv run pytest tests/test_models.py -v
```

Expected: all 8 tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/ice_gateway/models.py tests/test_models.py
git commit -m "feat: Pydantic models — SensorConfig, SensorReading, PiHealth"
```

---

## Task 4: Configuration

**Files:**
- Create: `src/ice_gateway/config.py`
- Create: `config/config.example.toml`
- Create: `.env.example`
- Create: `tests/fixtures/config_valid.toml`
- Create: `tests/fixtures/config_missing_sensor_id.toml`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests in `tests/test_config.py`**

```python
import shutil
import pytest
from pydantic import ValidationError
from ice_gateway.config import AppConfig


def test_config_loads_valid_toml(monkeypatch, tmp_path):
    (tmp_path / "config").mkdir()
    shutil.copy("tests/fixtures/config_valid.toml", tmp_path / "config" / "config.local.toml")
    (tmp_path / ".env").write_text("")
    monkeypatch.chdir(tmp_path)
    config = AppConfig()
    assert config.site_name == "Test Location"
    assert config.poll_interval_seconds == 30
    assert len(config.temperature_sensors) == 1
    assert config.temperature_sensors[0].id == "28-test000000"


def test_config_defaults_without_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    config = AppConfig()
    assert config.site_name == "Ice Gateway"
    assert config.poll_interval_seconds == 30


def test_config_sensor_missing_id_raises(monkeypatch, tmp_path):
    (tmp_path / "config").mkdir()
    shutil.copy(
        "tests/fixtures/config_missing_sensor_id.toml",
        tmp_path / "config" / "config.local.toml",
    )
    (tmp_path / ".env").write_text("")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValidationError):
        AppConfig()


def test_config_env_override(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SITE_NAME", "Override Site")
    config = AppConfig()
    assert config.site_name == "Override Site"
```

- [ ] **Step 2: Run tests and confirm they fail**

```bash
uv run pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'ice_gateway.config'`

- [ ] **Step 3: Write `src/ice_gateway/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from .models import SensorConfig


class NetworkConfig(BaseSettings):
    ksbu_private_interface: str = "eth0"
    ksbu_gateway_ip: str = "192.168.50.1"


class LoggingConfig(BaseSettings):
    level: str = "INFO"
    retain_days: int = 365


class DashboardConfig(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8080


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        toml_file="config/config.local.toml",
        env_file=".env",
        env_nested_delimiter="__",
        toml_file_encoding="utf-8",
    )

    site_name: str = "Ice Gateway"
    machine_name: str = "Scotsman Prodigy"
    timezone: str = "UTC"
    poll_interval_seconds: int = 30

    network: NetworkConfig = NetworkConfig()
    logging: LoggingConfig = LoggingConfig()
    dashboard: DashboardConfig = DashboardConfig()

    temperature_sensors: list[SensorConfig] = []
```

- [ ] **Step 4: Write `tests/fixtures/config_valid.toml`**

```toml
site_name = "Test Location"
machine_name = "Test Machine"
timezone = "UTC"
poll_interval_seconds = 30

[network]
ksbu_private_interface = "eth0"
ksbu_gateway_ip = "192.168.50.1"

[logging]
level = "DEBUG"
retain_days = 30

[dashboard]
host = "127.0.0.1"
port = 8080

[[temperature_sensors]]
id = "28-test000000"
name = "test_sensor"
location = "Test location"
enabled = true
```

- [ ] **Step 5: Write `tests/fixtures/config_missing_sensor_id.toml`**

```toml
site_name = "Bad Config"

[[temperature_sensors]]
name = "bin_upper_air"
location = "Bin"
enabled = true
```

- [ ] **Step 6: Write `config/config.example.toml`**

```toml
# Ice Gateway Configuration
# Copy to config/config.local.toml and edit for your site.

site_name = "My Ice Location"
machine_name = "Scotsman Prodigy"
timezone = "America/Kentucky/Louisville"
poll_interval_seconds = 30

[network]
ksbu_private_interface = "eth0"
ksbu_gateway_ip = "192.168.50.1"

[logging]
level = "INFO"
retain_days = 365

[dashboard]
host = "0.0.0.0"
port = 8080

# Add one [[temperature_sensors]] block per DS18B20 probe.
# Discover ROM IDs by running: ls /sys/bus/w1/devices/
[[temperature_sensors]]
id = "28-00000abc1234"
name = "bin_upper_air"
location = "Ice bin upper air"
enabled = true
alert_min_f = 25.0
alert_max_f = 45.0

[[temperature_sensors]]
id = "28-00000def5678"
name = "condenser_intake"
location = "Condenser intake air"
enabled = true
alert_min_f = 35.0
alert_max_f = 100.0
```

- [ ] **Step 7: Write `.env.example`**

```dotenv
# Ice Gateway secrets — copy to .env and fill in real values.
# Never commit .env to git.

# Required in Phase 3 (alerts):
# SMTP_PASSWORD=change-me
# TWILIO_AUTH_TOKEN=change-me
# MQTT_PASSWORD=change-me

# Override any AppConfig field via environment variable:
# SITE_NAME=My Location
# DASHBOARD__PORT=8080
```

- [ ] **Step 8: Run tests and confirm they pass**

```bash
uv run pytest tests/test_config.py -v
```

Expected: all 4 tests `PASSED`

- [ ] **Step 9: Remove the early-draft config file**

```bash
git rm config/ksbun_gateway.toml
```

- [ ] **Step 10: Commit**

```bash
git add src/ice_gateway/config.py config/ .env.example tests/fixtures/ tests/test_config.py
git commit -m "feat: AppConfig loading from TOML + env, replace ksbun_gateway.toml"
```

---

## Task 5: Database

**Files:**
- Create: `src/ice_gateway/database.py`
- Create: `tests/conftest.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Write the failing tests in `tests/test_database.py`**

```python
from datetime import datetime, timezone
from ice_gateway.database import SensorReadingRow, PiHealthRow, init_db
from ice_gateway.constants import ReadQuality
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_sensor_reading_round_trip(db_engine):
    with Session(db_engine) as session:
        row = SensorReadingRow(
            timestamp=_now(),
            sensor_id="28-abc123",
            sensor_name="bin_upper_air",
            temperature_c=2.5,
            temperature_f=36.5,
            read_quality=ReadQuality.OK.value,
            error_message=None,
        )
        session.add(row)
        session.commit()

        result = session.execute(select(SensorReadingRow)).scalar_one()
        assert result.sensor_id == "28-abc123"
        assert result.temperature_c == 2.5
        assert result.read_quality == "ok"


def test_pi_health_round_trip(db_engine):
    with Session(db_engine) as session:
        row = PiHealthRow(
            timestamp=_now(),
            cpu_temp_c=51.0,
            cpu_percent=10.0,
            memory_percent=40.0,
            disk_percent=20.0,
        )
        session.add(row)
        session.commit()

        result = session.execute(select(PiHealthRow)).scalar_one()
        assert result.cpu_temp_c == 51.0
        assert result.disk_percent == 20.0


def test_sensor_reading_allows_null_temperature(db_engine):
    with Session(db_engine) as session:
        row = SensorReadingRow(
            timestamp=_now(),
            sensor_id="28-abc123",
            sensor_name="bin_upper_air",
            temperature_c=None,
            temperature_f=None,
            read_quality=ReadQuality.MISSING.value,
            error_message="Device not found",
        )
        session.add(row)
        session.commit()

        result = session.execute(select(SensorReadingRow)).scalar_one()
        assert result.temperature_c is None
        assert result.error_message == "Device not found"
```

- [ ] **Step 2: Write `tests/conftest.py`** with the database fixtures these tests need

```python
import pytest
from sqlalchemy import create_engine
from ice_gateway.database import Base, init_db


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine):
    from sqlalchemy.orm import Session
    with Session(db_engine) as session:
        yield session
```

- [ ] **Step 3: Run tests and confirm they fail**

```bash
uv run pytest tests/test_database.py -v
```

Expected: `ModuleNotFoundError: No module named 'ice_gateway.database'`

- [ ] **Step 4: Write `src/ice_gateway/database.py`**

```python
from pathlib import Path
from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "ice_gateway.sqlite"


class Base(DeclarativeBase):
    pass


class SensorReadingRow(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    sensor_id = Column(String, nullable=False)
    sensor_name = Column(String, nullable=False)
    temperature_c = Column(Float, nullable=True)
    temperature_f = Column(Float, nullable=True)
    read_quality = Column(String, nullable=False)
    error_message = Column(String, nullable=True)


class PiHealthRow(Base):
    __tablename__ = "pi_health"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    cpu_temp_c = Column(Float, nullable=True)
    cpu_percent = Column(Float, nullable=False)
    memory_percent = Column(Float, nullable=False)
    disk_percent = Column(Float, nullable=False)


def create_db_engine(db_path: Path = DB_PATH):
    return create_engine(f"sqlite:///{db_path}", echo=False)


def init_db(engine) -> None:
    Base.metadata.create_all(engine)


def get_session(engine) -> Session:
    return Session(engine)
```

- [ ] **Step 5: Run tests and confirm they pass**

```bash
uv run pytest tests/test_database.py tests/test_models.py -v
```

Expected: all tests `PASSED`

- [ ] **Step 6: Commit**

```bash
git add src/ice_gateway/database.py tests/conftest.py tests/test_database.py
git commit -m "feat: SQLAlchemy ORM setup and database round-trip tests"
```

---

## Task 6: Logging Setup

**Files:**
- Create: `src/ice_gateway/logging_setup.py`

No unit tests — logging configuration is validated by observing output during integration. The `logs/` directory created in Task 1 is used at runtime.

- [ ] **Step 1: Write `src/ice_gateway/logging_setup.py`**

```python
import sys
from pathlib import Path
from loguru import logger

LOGS_DIR = Path("logs")


def configure_logging(level: str = "INFO", retain_days: int = 365) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )
    logger.add(
        LOGS_DIR / "ice_gateway.log",
        level=level,
        rotation="1 day",
        retention=f"{retain_days} days",
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
        encoding="utf-8",
    )
    logger.add(
        LOGS_DIR / "sensors.log",
        level=level,
        rotation="1 day",
        retention=f"{retain_days} days",
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
        filter=lambda record: "sensors" in record["name"],
        encoding="utf-8",
    )
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
uv run python -c "from ice_gateway.logging_setup import configure_logging; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/ice_gateway/logging_setup.py
git commit -m "feat: Loguru logging setup with daily rotation"
```

---

## Task 7: Sensor Base ABC and FakeSensorBus

**Files:**
- Create: `src/ice_gateway/sensors/base.py`
- Modify: `tests/conftest.py` — add `fake_sensor_bus` fixture

- [ ] **Step 1: Write `src/ice_gateway/sensors/base.py`**

```python
from abc import ABC, abstractmethod
from ..models import SensorConfig, SensorReading


class SensorBusReader(ABC):
    @abstractmethod
    def read_all(self, sensors: list[SensorConfig]) -> list[SensorReading]:
        """Read all enabled sensors. Never raises — returns error readings on failure."""
        ...
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
uv run python -c "from ice_gateway.sensors.base import SensorBusReader; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Append `FakeSensorBus` and `fake_sensor_bus` fixture to `tests/conftest.py`**

The `import pytest` at the top was added in Task 5. Add only the new imports and definitions:

```python
from ice_gateway.sensors.base import SensorBusReader
from ice_gateway.models import SensorConfig, SensorReading


class FakeSensorBus(SensorBusReader):
    def __init__(self, readings: list[SensorReading]) -> None:
        self._readings = readings

    def read_all(self, sensors: list[SensorConfig]) -> list[SensorReading]:
        return self._readings


@pytest.fixture
def fake_sensor_bus():
    def factory(readings: list[SensorReading]) -> FakeSensorBus:
        return FakeSensorBus(readings)
    return factory
```

- [ ] **Step 4: Confirm conftest imports cleanly (pytest collection)**

```bash
uv run pytest --collect-only tests/ 2>&1 | head -20
```

Expected: no import errors, test IDs listed.

- [ ] **Step 5: Commit**

```bash
git add src/ice_gateway/sensors/base.py tests/conftest.py
git commit -m "feat: SensorBusReader ABC and FakeSensorBus test fixture"
```

---

## Task 8: One-Wire Sensor Reader

**Files:**
- Create: `src/ice_gateway/sensors/onewire.py`
- Create: `tests/sensors/test_onewire.py`

- [ ] **Step 1: Write failing tests in `tests/sensors/test_onewire.py`**

```python
from datetime import datetime, timezone
from pathlib import Path
import pytest
from ice_gateway.sensors.onewire import OneWireSensorBusReader
from ice_gateway.models import SensorConfig
from ice_gateway.constants import ReadQuality


def _sensor(id: str = "28-abc123", name: str = "test") -> SensorConfig:
    return SensorConfig(id=id, name=name, location="test location")


def _make_reader(tmp_path: Path) -> OneWireSensorBusReader:
    return OneWireSensorBusReader(w1_devices_path=tmp_path)


def _write_sensor_file(tmp_path: Path, sensor_id: str, content: str) -> None:
    device_dir = tmp_path / sensor_id
    device_dir.mkdir()
    (device_dir / "w1_slave").write_text(content)


class TestOneWireSensorBusReader:
    def test_normal_read(self, tmp_path):
        _write_sensor_file(
            tmp_path,
            "28-abc123",
            "50 05 4b 46 7f ff 0c 10 1c : crc=1c YES\n"
            "50 05 4b 46 7f ff 0c 10 1c t=2500\n",
        )
        reader = _make_reader(tmp_path)
        readings = reader.read_all([_sensor()])
        assert len(readings) == 1
        assert readings[0].read_quality == ReadQuality.OK
        assert readings[0].temperature_c == pytest.approx(2.5)
        assert readings[0].temperature_f == pytest.approx(36.5)

    def test_missing_sensor(self, tmp_path):
        reader = _make_reader(tmp_path)
        readings = reader.read_all([_sensor(id="28-notfound")])
        assert readings[0].read_quality == ReadQuality.MISSING
        assert readings[0].temperature_c is None

    def test_crc_error(self, tmp_path):
        _write_sensor_file(
            tmp_path,
            "28-abc123",
            "50 05 4b 46 7f ff 0c 10 1c : crc=ff NO\n"
            "50 05 4b 46 7f ff 0c 10 1c t=2500\n",
        )
        reader = _make_reader(tmp_path)
        readings = reader.read_all([_sensor()])
        assert readings[0].read_quality == ReadQuality.CRC_ERROR
        assert readings[0].temperature_c is None

    def test_impossible_value(self, tmp_path):
        _write_sensor_file(
            tmp_path,
            "28-abc123",
            "50 05 4b 46 7f ff 0c 10 1c : crc=1c YES\n"
            "50 05 4b 46 7f ff 0c 10 1c t=999000\n",
        )
        reader = _make_reader(tmp_path)
        readings = reader.read_all([_sensor()])
        assert readings[0].read_quality == ReadQuality.IMPOSSIBLE_VALUE

    def test_disabled_sensor_skipped(self, tmp_path):
        sensor = SensorConfig(id="28-abc123", name="s", location="l", enabled=False)
        reader = _make_reader(tmp_path)
        readings = reader.read_all([sensor])
        assert readings == []

    def test_multiple_sensors(self, tmp_path):
        for sid, temp in [("28-aaa", "1000"), ("28-bbb", "2000")]:
            _write_sensor_file(
                tmp_path, sid,
                f"xx : crc=xx YES\nxx t={temp}\n",
            )
        reader = _make_reader(tmp_path)
        sensors = [_sensor(id="28-aaa", name="s1"), _sensor(id="28-bbb", name="s2")]
        readings = reader.read_all(sensors)
        assert len(readings) == 2
        assert readings[0].temperature_c == pytest.approx(1.0)
        assert readings[1].temperature_c == pytest.approx(2.0)
```

- [ ] **Step 2: Run tests and confirm they fail**

```bash
uv run pytest tests/sensors/test_onewire.py -v
```

Expected: `ModuleNotFoundError: No module named 'ice_gateway.sensors.onewire'`

- [ ] **Step 3: Write `src/ice_gateway/sensors/onewire.py`**

```python
from datetime import datetime, timezone
from pathlib import Path
from loguru import logger
from .base import SensorBusReader
from ..models import SensorConfig, SensorReading
from ..constants import ReadQuality

_DEFAULT_W1_PATH = Path("/sys/bus/w1/devices")
_TEMP_MIN_C = -55.0
_TEMP_MAX_C = 125.0


class OneWireSensorBusReader(SensorBusReader):
    def __init__(self, w1_devices_path: Path = _DEFAULT_W1_PATH) -> None:
        self._w1_path = w1_devices_path

    def read_all(self, sensors: list[SensorConfig]) -> list[SensorReading]:
        return [self._read(s) for s in sensors if s.enabled]

    def _read(self, sensor: SensorConfig) -> SensorReading:
        now = datetime.now(timezone.utc)
        device_file = self._w1_path / sensor.id / "w1_slave"

        if not device_file.exists():
            logger.warning("Sensor {name} ({id}) not found", name=sensor.name, id=sensor.id)
            return SensorReading(
                sensor_id=sensor.id,
                sensor_name=sensor.name,
                temperature_c=None,
                temperature_f=None,
                read_quality=ReadQuality.MISSING,
                error_message=f"Device file not found: {device_file}",
                timestamp=now,
            )

        try:
            raw = device_file.read_text()
        except OSError as exc:
            logger.error("Bus fault reading {name}: {exc}", name=sensor.name, exc=exc)
            return SensorReading(
                sensor_id=sensor.id,
                sensor_name=sensor.name,
                temperature_c=None,
                temperature_f=None,
                read_quality=ReadQuality.BUS_FAULT,
                error_message=str(exc),
                timestamp=now,
            )

        lines = raw.strip().splitlines()
        if len(lines) < 2 or "YES" not in lines[0]:
            logger.warning("CRC error for sensor {name}", name=sensor.name)
            return SensorReading(
                sensor_id=sensor.id,
                sensor_name=sensor.name,
                temperature_c=None,
                temperature_f=None,
                read_quality=ReadQuality.CRC_ERROR,
                error_message=f"CRC check failed: {raw!r}",
                timestamp=now,
            )

        try:
            temp_c = int(lines[1].split("t=")[1]) / 1000.0
        except (IndexError, ValueError) as exc:
            return SensorReading(
                sensor_id=sensor.id,
                sensor_name=sensor.name,
                temperature_c=None,
                temperature_f=None,
                read_quality=ReadQuality.BUS_FAULT,
                error_message=f"Failed to parse temperature: {exc}",
                timestamp=now,
            )

        if not (_TEMP_MIN_C <= temp_c <= _TEMP_MAX_C):
            logger.warning(
                "Impossible value from {name}: {temp}°C", name=sensor.name, temp=temp_c
            )
            return SensorReading(
                sensor_id=sensor.id,
                sensor_name=sensor.name,
                temperature_c=temp_c,
                temperature_f=temp_c * 9 / 5 + 32,
                read_quality=ReadQuality.IMPOSSIBLE_VALUE,
                error_message=f"Temperature {temp_c}°C outside valid range",
                timestamp=now,
            )

        return SensorReading(
            sensor_id=sensor.id,
            sensor_name=sensor.name,
            temperature_c=temp_c,
            temperature_f=temp_c * 9 / 5 + 32,
            read_quality=ReadQuality.OK,
            error_message=None,
            timestamp=now,
        )
```

- [ ] **Step 4: Run tests and confirm they pass**

```bash
uv run pytest tests/sensors/test_onewire.py -v
```

Expected: all 6 tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/ice_gateway/sensors/onewire.py tests/sensors/test_onewire.py
git commit -m "feat: OneWireSensorBusReader with full failure mode handling"
```

---

## Task 9: Pi Health Reader

**Files:**
- Create: `src/ice_gateway/sensors/pi_health.py`
- Create: `tests/sensors/test_pi_health.py`

- [ ] **Step 1: Write failing tests in `tests/sensors/test_pi_health.py`**

```python
from pathlib import Path
from unittest.mock import patch, MagicMock
from ice_gateway.sensors.pi_health import read_pi_health


class TestReadPiHealth:
    def test_returns_pi_health_object(self):
        result = read_pi_health()
        assert result.cpu_percent >= 0.0
        assert result.memory_percent >= 0.0
        assert result.disk_percent >= 0.0
        assert result.timestamp is not None

    def test_cpu_temp_none_when_file_missing(self, tmp_path):
        missing = tmp_path / "nonexistent"
        with patch("ice_gateway.sensors.pi_health._CPU_TEMP_PATH", missing):
            result = read_pi_health()
        assert result.cpu_temp_c is None

    def test_cpu_temp_parsed_correctly(self, tmp_path):
        temp_file = tmp_path / "temp"
        temp_file.write_text("52340\n")
        with patch("ice_gateway.sensors.pi_health._CPU_TEMP_PATH", temp_file):
            result = read_pi_health()
        assert result.cpu_temp_c == 52.34
```

- [ ] **Step 2: Run tests and confirm they fail**

```bash
uv run pytest tests/sensors/test_pi_health.py -v
```

Expected: `ModuleNotFoundError: No module named 'ice_gateway.sensors.pi_health'`

- [ ] **Step 3: Write `src/ice_gateway/sensors/pi_health.py`**

```python
from datetime import datetime, timezone
from pathlib import Path
import psutil
from loguru import logger
from ..models import PiHealth

_CPU_TEMP_PATH = Path("/sys/class/thermal/thermal_zone0/temp")


def read_pi_health() -> PiHealth:
    now = datetime.now(timezone.utc)

    cpu_temp_c: float | None = None
    try:
        cpu_temp_c = int(_CPU_TEMP_PATH.read_text().strip()) / 1000.0
    except (OSError, ValueError) as exc:
        logger.warning("Could not read CPU temperature: {exc}", exc=exc)

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return PiHealth(
        cpu_temp_c=cpu_temp_c,
        cpu_percent=psutil.cpu_percent(interval=0.1),
        memory_percent=memory.percent,
        disk_percent=disk.percent,
        timestamp=now,
    )
```

- [ ] **Step 4: Run tests and confirm they pass**

```bash
uv run pytest tests/sensors/ -v
```

Expected: all 9 tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/ice_gateway/sensors/pi_health.py tests/sensors/test_pi_health.py
git commit -m "feat: Pi health reader using psutil"
```

---

## Task 10: Dashboard

**Files:**
- Create: `src/ice_gateway/dashboard/app.py`
- Create: `src/ice_gateway/dashboard/routes.py`
- Create: `src/ice_gateway/dashboard/templates/base.html`
- Create: `src/ice_gateway/dashboard/templates/overview.html`
- Create: `src/ice_gateway/dashboard/static/style.css`
- Create: `tests/dashboard/test_routes.py`
- Modify: `tests/conftest.py` — add `app_client` fixture

- [ ] **Step 1: Write failing tests in `tests/dashboard/test_routes.py`**

```python
def test_overview_returns_200(app_client):
    response = app_client.get("/")
    assert response.status_code == 200
    assert "Ice Gateway" in response.text


def test_api_temperatures_returns_200(app_client):
    response = app_client.get("/api/temperatures")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_api_health_returns_200(app_client):
    response = app_client.get("/api/health")
    assert response.status_code == 200


def test_api_temperatures_empty_initially(app_client):
    response = app_client.get("/api/temperatures")
    assert response.json() == []


def test_api_health_empty_initially(app_client):
    response = app_client.get("/api/health")
    assert response.json() == {}
```

- [ ] **Step 2: Add `app_client` fixture to `tests/conftest.py`**

Append to the existing `tests/conftest.py`:

```python
from ice_gateway.dashboard.app import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def app_client(db_engine):
    app = create_app(db_engine)
    with TestClient(app) as client:
        yield client
```

- [ ] **Step 3: Run tests and confirm they fail**

```bash
uv run pytest tests/dashboard/test_routes.py -v
```

Expected: `ModuleNotFoundError: No module named 'ice_gateway.dashboard.app'`

- [ ] **Step 4: Write `src/ice_gateway/dashboard/app.py`**

```python
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def create_app(engine) -> FastAPI:
    app = FastAPI(title="Ice Gateway")
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    from .routes import create_router
    app.include_router(create_router(engine, templates))

    return app
```

- [ ] **Step 5: Write `src/ice_gateway/dashboard/routes.py`**

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from ..database import SensorReadingRow, PiHealthRow


def create_router(engine, templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()

    @router.get("/", response_class=HTMLResponse)
    def overview(request: Request):
        with Session(engine) as session:
            readings = session.execute(
                select(SensorReadingRow)
                .order_by(desc(SensorReadingRow.timestamp))
                .limit(50)
            ).scalars().all()
            health = session.execute(
                select(PiHealthRow).order_by(desc(PiHealthRow.timestamp)).limit(1)
            ).scalar_one_or_none()
        return templates.TemplateResponse(
            "overview.html", {"request": request, "readings": readings, "health": health}
        )

    @router.get("/api/temperatures")
    def api_temperatures():
        with Session(engine) as session:
            rows = session.execute(
                select(SensorReadingRow)
                .order_by(desc(SensorReadingRow.timestamp))
                .limit(50)
            ).scalars().all()
        return [
            {
                "sensor_id": r.sensor_id,
                "sensor_name": r.sensor_name,
                "temperature_c": r.temperature_c,
                "temperature_f": r.temperature_f,
                "read_quality": r.read_quality,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in rows
        ]

    @router.get("/api/health")
    def api_health():
        with Session(engine) as session:
            row = session.execute(
                select(PiHealthRow).order_by(desc(PiHealthRow.timestamp)).limit(1)
            ).scalar_one_or_none()
        if row is None:
            return {}
        return {
            "cpu_temp_c": row.cpu_temp_c,
            "cpu_percent": row.cpu_percent,
            "memory_percent": row.memory_percent,
            "disk_percent": row.disk_percent,
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
        }

    return router
```

- [ ] **Step 6: Write `src/ice_gateway/dashboard/templates/base.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Ice Gateway{% endblock %}</title>
    <link rel="stylesheet" href="/static/style.css">
    <meta http-equiv="refresh" content="30">
</head>
<body>
    <nav>
        <a href="/">Overview</a>
    </nav>
    <main>
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

- [ ] **Step 7: Write `src/ice_gateway/dashboard/templates/overview.html`**

```html
{% extends "base.html" %}
{% block title %}Overview — Ice Gateway{% endblock %}
{% block content %}
<h1>Ice Gateway Overview</h1>

<section>
    <h2>Pi Health</h2>
    {% if health %}
    <table>
        <tr><th>CPU Temp</th><td>{{ "%.1f"|format(health.cpu_temp_c) if health.cpu_temp_c is not none else "N/A" }} °C</td></tr>
        <tr><th>CPU Usage</th><td>{{ "%.1f"|format(health.cpu_percent) }}%</td></tr>
        <tr><th>Memory</th><td>{{ "%.1f"|format(health.memory_percent) }}%</td></tr>
        <tr><th>Disk</th><td>{{ "%.1f"|format(health.disk_percent) }}%</td></tr>
        <tr><th>Last Updated</th><td>{{ health.timestamp }}</td></tr>
    </table>
    {% else %}
    <p>No health data yet.</p>
    {% endif %}
</section>

<section>
    <h2>Temperature Sensors</h2>
    {% if readings %}
    <table>
        <tr><th>Sensor</th><th>°C</th><th>°F</th><th>Quality</th><th>Time</th></tr>
        {% for r in readings %}
        <tr>
            <td>{{ r.sensor_name }}</td>
            <td>{{ "%.2f"|format(r.temperature_c) if r.temperature_c is not none else "—" }}</td>
            <td>{{ "%.2f"|format(r.temperature_f) if r.temperature_f is not none else "—" }}</td>
            <td>{{ r.read_quality }}</td>
            <td>{{ r.timestamp }}</td>
        </tr>
        {% endfor %}
    </table>
    {% else %}
    <p>No sensor readings yet.</p>
    {% endif %}
</section>
{% endblock %}
```

- [ ] **Step 8: Write `src/ice_gateway/dashboard/static/style.css`**

```css
body {
    font-family: sans-serif;
    max-width: 960px;
    margin: 0 auto;
    padding: 1rem;
    background: #f5f5f5;
}

nav {
    background: #333;
    padding: 0.5rem 1rem;
    margin-bottom: 1rem;
    border-radius: 4px;
}

nav a { color: white; text-decoration: none; margin-right: 1rem; }

h1, h2 { color: #333; }

table {
    border-collapse: collapse;
    width: 100%;
    background: white;
    margin-bottom: 1rem;
}

th, td { border: 1px solid #ddd; padding: 0.5rem 1rem; text-align: left; }
th { background: #444; color: white; }
tr:nth-child(even) { background: #f9f9f9; }
section { margin-bottom: 2rem; }
```

- [ ] **Step 9: Run tests and confirm they pass**

```bash
uv run pytest tests/dashboard/test_routes.py -v
```

Expected: all 5 tests `PASSED`

- [ ] **Step 10: Commit**

```bash
git add src/ice_gateway/dashboard/ tests/dashboard/ tests/conftest.py
git commit -m "feat: FastAPI dashboard with overview page and JSON API endpoints"
```

---

## Task 11: Polling Loop

**Files:**
- Create: `src/ice_gateway/tasks/polling.py`

The polling loop is exercised by the full test suite via integration — no isolated unit tests at Phase 1 (the subsystems it calls are already tested individually).

- [ ] **Step 1: Write `src/ice_gateway/tasks/polling.py`**

```python
import asyncio
from loguru import logger
from sqlalchemy.orm import Session
from ..sensors.base import SensorBusReader
from ..sensors.pi_health import read_pi_health
from ..database import SensorReadingRow, PiHealthRow
from ..config import AppConfig


async def polling_loop(config: AppConfig, engine, sensor_bus: SensorBusReader) -> None:
    logger.info(
        "Polling loop started — interval={interval}s, sensors={count}",
        interval=config.poll_interval_seconds,
        count=len(config.temperature_sensors),
    )
    while True:
        try:
            _poll_once(config, engine, sensor_bus)
        except Exception as exc:
            logger.error("Unexpected error in polling loop: {exc}", exc=exc)
        await asyncio.sleep(config.poll_interval_seconds)


def _poll_once(config: AppConfig, engine, sensor_bus: SensorBusReader) -> None:
    readings = sensor_bus.read_all(config.temperature_sensors)
    health = read_pi_health()

    with Session(engine) as session:
        for r in readings:
            session.add(
                SensorReadingRow(
                    timestamp=r.timestamp,
                    sensor_id=r.sensor_id,
                    sensor_name=r.sensor_name,
                    temperature_c=r.temperature_c,
                    temperature_f=r.temperature_f,
                    read_quality=r.read_quality.value,
                    error_message=r.error_message,
                )
            )
        session.add(
            PiHealthRow(
                timestamp=health.timestamp,
                cpu_temp_c=health.cpu_temp_c,
                cpu_percent=health.cpu_percent,
                memory_percent=health.memory_percent,
                disk_percent=health.disk_percent,
            )
        )
        session.commit()

    logger.info("Poll complete — {count} sensor reading(s) written", count=len(readings))
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
uv run python -c "from ice_gateway.tasks.polling import polling_loop; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/ice_gateway/tasks/polling.py
git commit -m "feat: asyncio polling loop — sensors and Pi health to SQLite"
```

---

## Task 12: Main Entry Point

**Files:**
- Create: `src/ice_gateway/main.py`
- Delete: `main.py` (root-level placeholder)

- [ ] **Step 1: Delete the root-level placeholder `main.py`**

```bash
git rm main.py
```

- [ ] **Step 2: Write `src/ice_gateway/main.py`**

```python
import asyncio
from pathlib import Path
from loguru import logger
import uvicorn
from .config import AppConfig
from .logging_setup import configure_logging
from .database import create_db_engine, init_db
from .sensors.onewire import OneWireSensorBusReader
from .dashboard.app import create_app
from .tasks.polling import polling_loop


def main() -> None:
    config = AppConfig()
    configure_logging(config.logging.level, config.logging.retain_days)
    logger.info("Starting Ice Gateway — site={site}", site=config.site_name)

    engine = create_db_engine()
    init_db(engine)
    logger.info("Database ready")

    asyncio.run(_run(config, engine))


async def _run(config: AppConfig, engine) -> None:
    sensor_bus = OneWireSensorBusReader()
    app = create_app(engine)

    server = uvicorn.Server(
        uvicorn.Config(
            app=app,
            host=config.dashboard.host,
            port=config.dashboard.port,
            log_level="warning",
        )
    )

    await asyncio.gather(
        polling_loop(config, engine, sensor_bus),
        server.serve(),
    )
```

- [ ] **Step 3: Verify the entry point resolves**

```bash
uv run ice-gateway --help 2>&1 || uv run python -c "from ice_gateway.main import main; print('ok')"
```

Expected: `ok` (the process will start and try to connect to real sensors; Ctrl-C is fine)

- [ ] **Step 4: Run the full test suite**

```bash
uv run pytest --cov=src/ice_gateway --cov-report=term-missing -v
```

Expected: all tests pass, coverage ≥ 80% on `src/ice_gateway/`.

- [ ] **Step 5: Commit**

```bash
git add src/ice_gateway/main.py
git commit -m "feat: main entry point wiring polling loop and dashboard"
```

---

## Task 13: Systemd Service

**Files:**
- Create: `systemd/ice-gateway.service`

- [ ] **Step 1: Write `systemd/ice-gateway.service`**

```ini
[Unit]
Description=Ice Gateway Monitor
Documentation=https://github.com/your-repo/scotsman-monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/ice_gateway
EnvironmentFile=/etc/ice-gateway/ice-gateway.env
ExecStart=/home/pi/.local/bin/uv run ice-gateway
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ice-gateway

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Commit**

```bash
git add systemd/ice-gateway.service
git commit -m "feat: systemd unit for ice-gateway service"
```

---

## Task 14: Setup Scripts

**Files:**
- Create: `scripts/00_README.sh`
- Create: `scripts/01_setup_os.sh`
- Create: `scripts/02_setup_network.sh`
- Create: `scripts/03_setup_tailscale.sh`
- Create: `scripts/04_setup_onewire.sh`
- Create: `scripts/05_setup_python.sh`
- Create: `scripts/06_deploy_app.sh`

- [ ] **Step 1: Write `scripts/00_README.sh`**

```bash
#!/bin/bash
cat << 'EOF'
=== Ice Gateway Setup Guide ===

Run these scripts in order on a fresh Raspberry Pi OS (64-bit) installation:

  sudo bash scripts/01_setup_os.sh        # Update OS, install base packages
  sudo bash scripts/02_setup_network.sh   # Static IP on eth0, UFW firewall
  sudo bash scripts/03_setup_tailscale.sh # Install Tailscale (requires auth key)
  sudo bash scripts/04_setup_onewire.sh   # Enable DS18B20 1-wire sensors
       bash scripts/05_setup_python.sh    # Install uv and Python dependencies
  sudo bash scripts/06_deploy_app.sh      # Deploy app, install systemd service

After all scripts:
  1. Edit /opt/ice_gateway/config/config.local.toml — add sensor ROM IDs and site name
  2. Edit /etc/ice-gateway/ice-gateway.env — add any secrets
  3. sudo systemctl restart ice-gateway
  4. sudo reboot   (required for 1-wire overlay to activate)

Verify:
  systemctl status ice-gateway
  tailscale status
  ls /sys/bus/w1/devices/
  curl http://localhost:8080/api/health
EOF

echo ""
echo "Checking repository files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

for f in 01_setup_os.sh 02_setup_network.sh 03_setup_tailscale.sh \
          04_setup_onewire.sh 05_setup_python.sh 06_deploy_app.sh; do
    if [ -f "$PROJECT_DIR/scripts/$f" ]; then
        echo "  OK  $f"
    else
        echo "  MISSING  $f"
    fi
done
```

- [ ] **Step 2: Write `scripts/01_setup_os.sh`**

```bash
#!/bin/bash
set -euo pipefail

echo "=== Step 1: OS Setup ==="
apt-get update
apt-get upgrade -y
apt-get install -y git sqlite3 i2c-tools chrony ufw openssh-server

timedatectl set-timezone UTC

systemctl enable ssh
systemctl start ssh

systemctl enable chrony
systemctl start chrony

echo "=== OS setup complete ==="
```

- [ ] **Step 3: Write `scripts/02_setup_network.sh`**

```bash
#!/bin/bash
set -euo pipefail

echo "=== Step 2: Network Setup ==="

# Static IP on eth0 for KSBU-N private subnet
if ! grep -q "interface eth0" /etc/dhcpcd.conf; then
    cat >> /etc/dhcpcd.conf << 'EOF'

# KSBU-N private subnet — added by ice-gateway setup
interface eth0
static ip_address=192.168.50.1/24
norouter
nogateway
EOF
    echo "Added static eth0 config to /etc/dhcpcd.conf"
else
    echo "eth0 static config already present"
fi

systemctl restart dhcpcd || true

# Firewall
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 8080/tcp comment 'Ice Gateway Dashboard'
ufw --force enable

echo "=== Network setup complete ==="
```

- [ ] **Step 4: Write `scripts/03_setup_tailscale.sh`**

```bash
#!/bin/bash
set -euo pipefail

echo "=== Step 3: Tailscale Setup ==="

curl -fsSL https://tailscale.com/install.sh | sh

echo ""
echo "Enter your Tailscale auth key (from https://login.tailscale.com/admin/settings/keys):"
read -r -s TAILSCALE_AUTH_KEY

tailscale up --authkey="$TAILSCALE_AUTH_KEY" --hostname="ice-gateway-$(hostname)"

echo ""
echo "=== Tailscale setup complete ==="
echo "Tailscale IP: $(tailscale ip -4 2>/dev/null || echo 'pending')"
```

- [ ] **Step 5: Write `scripts/04_setup_onewire.sh`**

```bash
#!/bin/bash
set -euo pipefail

echo "=== Step 4: One-Wire (DS18B20) Setup ==="

CONFIG_FILE="/boot/firmware/config.txt"

if [ ! -f "$CONFIG_FILE" ]; then
    # Older Raspberry Pi OS path
    CONFIG_FILE="/boot/config.txt"
fi

if ! grep -q "dtoverlay=w1-gpio" "$CONFIG_FILE"; then
    echo "" >> "$CONFIG_FILE"
    echo "# DS18B20 One-Wire temperature sensors" >> "$CONFIG_FILE"
    echo "dtoverlay=w1-gpio,gpiopin=4" >> "$CONFIG_FILE"
    echo "Added 1-wire overlay to $CONFIG_FILE"
else
    echo "1-wire overlay already present in $CONFIG_FILE"
fi

modprobe w1-gpio 2>/dev/null || true
modprobe w1-therm 2>/dev/null || true

echo "=== One-Wire setup complete. REBOOT REQUIRED for permanent effect. ==="
echo "After reboot, sensor ROM IDs will appear in: ls /sys/bus/w1/devices/"
```

- [ ] **Step 6: Write `scripts/05_setup_python.sh`**

```bash
#!/bin/bash
set -euo pipefail

echo "=== Step 5: Python/uv Setup ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

export PATH="$HOME/.local/bin:$PATH"

cd "$PROJECT_DIR"
uv sync

echo "=== Python setup complete ==="
echo "Test: uv run python -c \"from ice_gateway.main import main; print('ok')\""
```

- [ ] **Step 7: Write `scripts/06_deploy_app.sh`**

```bash
#!/bin/bash
set -euo pipefail

echo "=== Step 6: Deploy Application ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
APP_DIR="/opt/ice_gateway"
ENV_FILE="/etc/ice-gateway/ice-gateway.env"

# Copy project to /opt
mkdir -p "$APP_DIR"
rsync -a --exclude='.git' --exclude='.venv' "$PROJECT_DIR/" "$APP_DIR/"

# Re-sync dependencies in the installed location
cd "$APP_DIR"
export PATH="$HOME/.local/bin:$PATH"
uv sync

# Create config.local.toml if missing
if [ ! -f "$APP_DIR/config/config.local.toml" ]; then
    cp "$APP_DIR/config/config.example.toml" "$APP_DIR/config/config.local.toml"
    echo "Created config.local.toml — edit $APP_DIR/config/config.local.toml before starting"
fi

# Create env file if missing
mkdir -p "$(dirname "$ENV_FILE")"
if [ ! -f "$ENV_FILE" ]; then
    cp "$APP_DIR/.env.example" "$ENV_FILE"
    echo "Created $ENV_FILE — edit with your secrets"
fi

# Install and start systemd service
cp "$APP_DIR/systemd/ice-gateway.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable ice-gateway
systemctl start ice-gateway

echo ""
echo "=== Deployment complete ==="
systemctl status ice-gateway --no-pager
```

- [ ] **Step 8: Make all scripts executable and commit**

```bash
chmod +x scripts/*.sh
git add scripts/
git commit -m "feat: Pi setup scripts 00-06"
```

---

## Final Verification

- [ ] **Run the complete test suite with coverage**

```bash
uv run pytest --cov=src/ice_gateway --cov-report=term-missing --cov-fail-under=80 -v
```

Expected: all tests pass, coverage ≥ 80%.

- [ ] **Run ruff lint and format check**

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

Expected: no errors.

- [ ] **Run mypy type check**

```bash
uv run mypy src/ice_gateway --strict --no-error-summary
```

Expected: `Success: no issues found`

- [ ] **Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: address ruff/mypy issues from final verification"
```
