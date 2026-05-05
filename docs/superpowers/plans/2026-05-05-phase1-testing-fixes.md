# Phase 1 Testing Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all Critical and Important issues from the Phase 1 code review — introduce `PiHealthProvider` ABC with constructor injection, add stub ABCs for Phase 2 interfaces, fix `DateTime` timezone handling, and close all identified test coverage gaps.

**Architecture:** Every hardware boundary gets an ABC in `sensors/base.py` with a concrete implementation in its own module and a fake in `tests/conftest.py`. Production code receives concrete implementations via constructor injection; tests receive fakes. No `patch()` calls for hardware boundaries.

**Tech Stack:** Python 3.11+, pytest + pytest-asyncio (`asyncio_mode = "auto"`), SQLAlchemy, FastAPI TestClient, psutil, uv

---

## Files Modified

| File | Change |
|---|---|
| `src/ice_gateway/sensors/base.py` | Add `PiHealthProvider`, `UPSStatusProvider`, `KSBUNTransport`, `GPIOController` ABCs |
| `src/ice_gateway/sensors/pi_health.py` | Replace bare function with `PsutilPiHealthProvider` class |
| `src/ice_gateway/tasks/polling.py` | Add `pi_health_provider` parameter to `_poll_once` and `polling_loop` |
| `src/ice_gateway/main.py` | Construct `PsutilPiHealthProvider`, pass to `polling_loop` |
| `src/ice_gateway/database.py` | Add `timezone=True` to both `DateTime` columns |
| `tests/conftest.py` | Add `FakePiHealthProvider`, `FakeUPS`, `FakeGPIO`, `FakeKSBUNTransport`, `fake_pi_health_provider` fixture |
| `tests/sensors/test_pi_health.py` | Rewrite using constructor injection — zero `patch()` calls |
| `tests/tasks/test_polling.py` | Use `fake_pi_health_provider`; add `polling_loop` exception test |
| `tests/dashboard/test_routes.py` | Add two tests that insert rows then call API |
| `tests/sensors/test_onewire.py` | Add OSError and parse-failure tests |
| `tests/test_database.py` | Add timezone round-trip test |

---

## Task 1: Add `PiHealthProvider` ABC and Phase 2 stub ABCs to `sensors/base.py`

**Files:**
- Modify: `src/ice_gateway/sensors/base.py`

- [ ] **Step 1: Verify the ABC does not yet exist**

```bash
uv run python -c "from ice_gateway.sensors.base import PiHealthProvider"
```
Expected: `ImportError: cannot import name 'PiHealthProvider'`

- [ ] **Step 2: Add ABCs to `sensors/base.py`**

Replace the entire file with:

```python
from abc import ABC, abstractmethod

from ..models import PiHealth, SensorConfig, SensorReading


class SensorBusReader(ABC):
    @abstractmethod
    def read_all(self, sensors: list[SensorConfig]) -> list[SensorReading]:
        """Read all enabled sensors. Returns error readings on failure, never raises."""
        ...


class PiHealthProvider(ABC):
    @abstractmethod
    def read(self) -> PiHealth:
        ...


class UPSStatusProvider(ABC):
    pass


class KSBUNTransport(ABC):
    pass


class GPIOController(ABC):
    pass
```

- [ ] **Step 3: Verify imports resolve**

```bash
uv run python -c "from ice_gateway.sensors.base import PiHealthProvider, UPSStatusProvider, KSBUNTransport, GPIOController; print('ok')"
```
Expected: `ok`

- [ ] **Step 4: Run the full test suite — all 35 tests should still pass**

```bash
uv run pytest -q
```
Expected: `35 passed`

- [ ] **Step 5: Commit**

```bash
git add src/ice_gateway/sensors/base.py
git commit -m "feat: add PiHealthProvider ABC and Phase 2 stub ABCs to sensors/base"
```

---

## Task 2: Replace `read_pi_health()` with `PsutilPiHealthProvider` class

**Files:**
- Modify: `src/ice_gateway/sensors/pi_health.py`
- Modify: `tests/sensors/test_pi_health.py`

The existing `test_pi_health.py` tests patch internals. We rewrite them first (they will fail because `PsutilPiHealthProvider` doesn't exist yet), then implement the class.

- [ ] **Step 1: Rewrite `tests/sensors/test_pi_health.py` to use constructor injection**

Replace the entire file with:

```python
import pytest

from ice_gateway.sensors.pi_health import PsutilPiHealthProvider


class TestPsutilPiHealthProvider:
    def test_returns_pi_health_object(self, tmp_path):
        temp_file = tmp_path / "temp"
        temp_file.write_text("52000\n")
        provider = PsutilPiHealthProvider(cpu_temp_path=temp_file)
        result = provider.read()
        assert result.cpu_temp_c == pytest.approx(52.0)
        assert result.cpu_percent >= 0.0
        assert result.memory_percent > 0.0
        assert result.disk_percent > 0.0
        assert result.timestamp is not None

    def test_cpu_temp_none_when_file_missing(self, tmp_path):
        provider = PsutilPiHealthProvider(cpu_temp_path=tmp_path / "nonexistent")
        result = provider.read()
        assert result.cpu_temp_c is None

    def test_cpu_temp_parsed_correctly(self, tmp_path):
        temp_file = tmp_path / "temp"
        temp_file.write_text("52340\n")
        provider = PsutilPiHealthProvider(cpu_temp_path=temp_file)
        result = provider.read()
        assert result.cpu_temp_c == pytest.approx(52.34)
```

- [ ] **Step 2: Run the new tests to confirm they fail**

```bash
uv run pytest tests/sensors/test_pi_health.py -v
```
Expected: `ImportError: cannot import name 'PsutilPiHealthProvider'`

- [ ] **Step 3: Rewrite `src/ice_gateway/sensors/pi_health.py`**

Replace the entire file with:

```python
from datetime import UTC, datetime
from pathlib import Path

import psutil
from loguru import logger

from ..models import PiHealth
from .base import PiHealthProvider

_DEFAULT_CPU_TEMP_PATH = Path("/sys/class/thermal/thermal_zone0/temp")


class PsutilPiHealthProvider(PiHealthProvider):
    def __init__(self, cpu_temp_path: Path = _DEFAULT_CPU_TEMP_PATH) -> None:
        self._cpu_temp_path = cpu_temp_path

    def read(self) -> PiHealth:
        now = datetime.now(UTC)

        cpu_temp_c: float | None = None
        try:
            cpu_temp_c = int(self._cpu_temp_path.read_text().strip()) / 1000.0
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

- [ ] **Step 4: Run the pi_health tests — they should now pass**

```bash
uv run pytest tests/sensors/test_pi_health.py -v
```
Expected: `3 passed`

- [ ] **Step 5: Run the full suite — expect failures in test_polling.py (it still patches the old function)**

```bash
uv run pytest -q
```
Expected: failures in `tests/tasks/test_polling.py` because it imports `read_pi_health` which no longer exists. That is expected — it will be fixed in Task 4.

- [ ] **Step 6: Commit**

```bash
git add src/ice_gateway/sensors/pi_health.py tests/sensors/test_pi_health.py
git commit -m "feat: replace read_pi_health() with PsutilPiHealthProvider ABC implementation"
```

---

## Task 3: Update `conftest.py` with fakes and `fake_pi_health_provider` fixture

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Replace `tests/conftest.py` with the expanded version**

```python
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from ice_gateway.dashboard.app import create_app
from ice_gateway.database import Base, init_db
from ice_gateway.models import PiHealth, SensorConfig, SensorReading
from ice_gateway.sensors.base import (
    GPIOController,
    KSBUNTransport,
    PiHealthProvider,
    SensorBusReader,
    UPSStatusProvider,
)

_DEFAULT_FAKE_HEALTH = PiHealth(
    cpu_temp_c=45.0,
    cpu_percent=10.0,
    memory_percent=40.0,
    disk_percent=20.0,
    timestamp=datetime(2024, 1, 1, tzinfo=UTC),
)


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    with Session(db_engine) as session:
        yield session


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


class FakePiHealthProvider(PiHealthProvider):
    def __init__(self, result: PiHealth = _DEFAULT_FAKE_HEALTH) -> None:
        self._result = result

    def read(self) -> PiHealth:
        return self._result


class FakeUPS(UPSStatusProvider):
    pass


class FakeGPIO(GPIOController):
    pass


class FakeKSBUNTransport(KSBUNTransport):
    pass


@pytest.fixture
def fake_pi_health_provider() -> FakePiHealthProvider:
    return FakePiHealthProvider()


@pytest.fixture
def app_client(db_engine):
    app = create_app(db_engine)
    with TestClient(app) as client:
        yield client
```

- [ ] **Step 2: Verify conftest imports cleanly**

```bash
uv run python -c "import tests.conftest; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "feat: add FakePiHealthProvider, FakeUPS, FakeGPIO, FakeKSBUNTransport to conftest"
```

---

## Task 4: Inject `PiHealthProvider` into `polling.py`, update `main.py`, fix `test_polling.py`

**Files:**
- Modify: `src/ice_gateway/tasks/polling.py`
- Modify: `src/ice_gateway/main.py`
- Modify: `tests/tasks/test_polling.py`

- [ ] **Step 1: Update the three existing tests in `test_polling.py` to use injection**

Replace the entire `tests/tasks/test_polling.py` with (includes all imports needed by Task 5 too):

```python
import asyncio
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from ice_gateway.config import AppConfig
from ice_gateway.constants import ReadQuality
from ice_gateway.database import PiHealthRow, SensorReadingRow
from ice_gateway.models import PiHealth, SensorReading
from ice_gateway.sensors.base import PiHealthProvider
from ice_gateway.tasks.polling import _poll_once, polling_loop


def _now() -> datetime:
    return datetime.now(UTC)


def _make_reading(sensor_id: str = "28-abc") -> SensorReading:
    return SensorReading(
        sensor_id=sensor_id,
        sensor_name="test_sensor",
        temperature_c=2.5,
        temperature_f=36.5,
        read_quality=ReadQuality.OK,
        timestamp=_now(),
    )


@pytest.fixture
def config(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    return AppConfig()


def test_poll_once_writes_sensor_reading(config, db_engine, fake_sensor_bus, fake_pi_health_provider):
    reading = _make_reading()
    bus = fake_sensor_bus([reading])

    _poll_once(config, db_engine, bus, fake_pi_health_provider)

    with Session(db_engine) as session:
        rows = session.execute(select(SensorReadingRow)).scalars().all()
    assert len(rows) == 1
    assert rows[0].sensor_id == "28-abc"
    assert rows[0].temperature_c == 2.5
    assert rows[0].read_quality == "ok"


def test_poll_once_writes_pi_health(config, db_engine, fake_sensor_bus, fake_pi_health_provider):
    bus = fake_sensor_bus([])

    _poll_once(config, db_engine, bus, fake_pi_health_provider)

    with Session(db_engine) as session:
        row = session.execute(select(PiHealthRow)).scalar_one()
    assert row.cpu_temp_c == 45.0
    assert row.cpu_percent == 10.0


def test_poll_once_multiple_readings(config, db_engine, fake_sensor_bus, fake_pi_health_provider):
    readings = [_make_reading("28-aaa"), _make_reading("28-bbb")]
    bus = fake_sensor_bus(readings)

    _poll_once(config, db_engine, bus, fake_pi_health_provider)

    with Session(db_engine) as session:
        rows = session.execute(select(SensorReadingRow)).scalars().all()
    assert len(rows) == 2
    assert {r.sensor_id for r in rows} == {"28-aaa", "28-bbb"}
```

- [ ] **Step 2: Run the tests — they should fail because `_poll_once` still has the old signature**

```bash
uv run pytest tests/tasks/test_polling.py -v
```
Expected: `TypeError: _poll_once() takes 3 positional arguments but 4 were given`

- [ ] **Step 3: Replace `src/ice_gateway/tasks/polling.py`**

```python
import asyncio

from loguru import logger
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ..config import AppConfig
from ..database import PiHealthRow, SensorReadingRow
from ..sensors.base import PiHealthProvider, SensorBusReader


async def polling_loop(
    config: AppConfig,
    engine: Engine,
    sensor_bus: SensorBusReader,
    pi_health_provider: PiHealthProvider,
) -> None:
    logger.info(
        "Polling loop started — interval={interval}s, sensors={count}",
        interval=config.poll_interval_seconds,
        count=len(config.temperature_sensors),
    )
    while True:
        try:
            _poll_once(config, engine, sensor_bus, pi_health_provider)
        except Exception:
            logger.exception("Unexpected error in polling loop")
        await asyncio.sleep(config.poll_interval_seconds)


def _poll_once(
    config: AppConfig,
    engine: Engine,
    sensor_bus: SensorBusReader,
    pi_health_provider: PiHealthProvider,
) -> None:
    readings = sensor_bus.read_all(config.temperature_sensors)
    health = pi_health_provider.read()

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

    logger.info(
        "Poll complete — {count} sensor reading(s) written", count=len(readings)
    )
```

- [ ] **Step 4: Update `src/ice_gateway/main.py` to construct and inject `PsutilPiHealthProvider`**

Replace the entire file with:

```python
import asyncio

import uvicorn
from loguru import logger
from sqlalchemy.engine import Engine

from .config import AppConfig
from .dashboard.app import create_app
from .database import create_db_engine, init_db
from .logging_setup import configure_logging
from .sensors.onewire import OneWireSensorBusReader
from .sensors.pi_health import PsutilPiHealthProvider
from .tasks.polling import polling_loop


def main() -> None:
    config = AppConfig()
    configure_logging(config.logging.level, config.logging.retain_days)
    logger.info("Starting Ice Gateway — site={site}", site=config.site_name)

    engine = create_db_engine()
    init_db(engine)
    logger.info("Database ready")

    asyncio.run(_run(config, engine))


async def _run(config: AppConfig, engine: Engine) -> None:
    sensor_bus = OneWireSensorBusReader()
    pi_health_provider = PsutilPiHealthProvider()
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
        polling_loop(config, engine, sensor_bus, pi_health_provider),
        server.serve(),
    )
```

- [ ] **Step 5: Run the full test suite — all tests should pass**

```bash
uv run pytest -q
```
Expected: `38 passed` (35 original + 3 rewritten pi_health tests)

- [ ] **Step 6: Commit**

```bash
git add src/ice_gateway/tasks/polling.py src/ice_gateway/main.py tests/tasks/test_polling.py
git commit -m "feat: inject PiHealthProvider into polling_loop and _poll_once; remove read_pi_health patch"
```

---

## Task 5: Add `polling_loop` exception-swallowing async test

**Files:**
- Modify: `tests/tasks/test_polling.py`

The loop's `except Exception` block is currently uncovered. This test verifies that a crash in `_poll_once` does not kill the loop.

- [ ] **Step 1: Append the new async test to `tests/tasks/test_polling.py`**

All needed imports (`asyncio`, `patch`, `polling_loop`, `PiHealthProvider`) are already present from Task 4's file replacement. Just append this test at the bottom of the file:

```python
async def test_polling_loop_continues_after_exception(
    config, db_engine, fake_sensor_bus
):
    call_count = 0
    good_health = PiHealth(
        cpu_temp_c=50.0,
        cpu_percent=10.0,
        memory_percent=40.0,
        disk_percent=20.0,
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
    )

    class RaisingThenOkProvider(PiHealthProvider):
        def read(self) -> PiHealth:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("simulated crash")
            return good_health

    bus = fake_sensor_bus([])
    provider = RaisingThenOkProvider()
    sleep_calls = 0

    async def fake_sleep(_seconds: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls >= 2:
            raise asyncio.CancelledError()

    with patch("asyncio.sleep", new=fake_sleep):
        with pytest.raises(asyncio.CancelledError):
            await polling_loop(config, db_engine, bus, provider)

    with Session(db_engine) as session:
        rows = session.execute(select(PiHealthRow)).scalars().all()
    assert len(rows) == 1
```

- [ ] **Step 2: Run the new test**

```bash
uv run pytest tests/tasks/test_polling.py::test_polling_loop_continues_after_exception -v
```
Expected: `PASSED`

- [ ] **Step 3: Run the full suite**

```bash
uv run pytest -q
```
Expected: `39 passed`

- [ ] **Step 4: Commit**

```bash
git add tests/tasks/test_polling.py
git commit -m "test: verify polling_loop swallows exceptions and continues iterating"
```

---

## Task 6: Fix `DateTime(timezone=True)` in `database.py` and add round-trip test

**Files:**
- Modify: `src/ice_gateway/database.py`
- Modify: `tests/test_database.py`

- [ ] **Step 1: Write the failing timezone round-trip test**

Append to `tests/test_database.py`:

```python
def test_timestamp_preserves_timezone(db_engine):
    ts = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
    with Session(db_engine) as session:
        session.add(
            SensorReadingRow(
                timestamp=ts,
                sensor_id="28-tz-test",
                sensor_name="tz_sensor",
                temperature_c=5.0,
                temperature_f=41.0,
                read_quality=ReadQuality.OK.value,
            )
        )
        session.commit()
        result = session.execute(select(SensorReadingRow)).scalar_one()
        assert result.timestamp.tzinfo is not None
```

- [ ] **Step 2: Run the new test to confirm it fails**

```bash
uv run pytest tests/test_database.py::test_timestamp_preserves_timezone -v
```
Expected: `FAILED` — `AssertionError: assert None is not None` (naive datetime returned)

- [ ] **Step 3: Fix both `DateTime` columns in `src/ice_gateway/database.py`**

Change line 19 (SensorReadingRow timestamp):
```python
    timestamp = Column(DateTime(timezone=True), nullable=False)
```

Change line 32 (PiHealthRow timestamp):
```python
    timestamp = Column(DateTime(timezone=True), nullable=False)
```

The full updated `database.py`:

```python
from pathlib import Path

from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "ice_gateway.sqlite"


class Base(DeclarativeBase):
    pass


class SensorReadingRow(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    sensor_id = Column(String, nullable=False)
    sensor_name = Column(String, nullable=False)
    temperature_c = Column(Float, nullable=True)
    temperature_f = Column(Float, nullable=True)
    read_quality = Column(String, nullable=False)
    error_message = Column(String, nullable=True)


class PiHealthRow(Base):
    __tablename__ = "pi_health"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    cpu_temp_c = Column(Float, nullable=True)
    cpu_percent = Column(Float, nullable=False)
    memory_percent = Column(Float, nullable=False)
    disk_percent = Column(Float, nullable=False)


def create_db_engine(db_path: Path = DB_PATH) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", echo=False)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def get_session(engine: Engine) -> Session:
    return Session(engine)
```

- [ ] **Step 4: Run the timezone test — it should now pass**

```bash
uv run pytest tests/test_database.py::test_timestamp_preserves_timezone -v
```
Expected: `PASSED`

- [ ] **Step 5: Run the full suite**

```bash
uv run pytest -q
```
Expected: `40 passed`

- [ ] **Step 6: Commit**

```bash
git add src/ice_gateway/database.py tests/test_database.py
git commit -m "fix: add timezone=True to DateTime columns; add timezone round-trip test"
```

---

## Task 7: Add dashboard tests with data in the database

**Files:**
- Modify: `tests/dashboard/test_routes.py`

Both `app_client` and `db_session` use the same `db_engine` fixture instance (pytest reuses it within the same test). `StaticPool` ensures the in-memory SQLite connection is shared, so rows committed via `db_session` are immediately visible to the app.

- [ ] **Step 1: Append two new tests to `tests/dashboard/test_routes.py`**

Add these imports at the top of the file:

```python
from datetime import UTC, datetime

from ice_gateway.constants import ReadQuality
from ice_gateway.database import PiHealthRow, SensorReadingRow
```

Then append at the bottom:

```python
def test_api_temperatures_returns_data(app_client, db_session):
    db_session.add(
        SensorReadingRow(
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            sensor_id="28-abc",
            sensor_name="freezer",
            temperature_c=-5.0,
            temperature_f=23.0,
            read_quality=ReadQuality.OK.value,
            error_message=None,
        )
    )
    db_session.commit()
    response = app_client.get("/api/temperatures")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["sensor_id"] == "28-abc"
    assert data[0]["temperature_c"] == -5.0
    assert data[0]["read_quality"] == "ok"


def test_api_health_returns_data(app_client, db_session):
    db_session.add(
        PiHealthRow(
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            cpu_temp_c=50.0,
            cpu_percent=42.0,
            memory_percent=35.0,
            disk_percent=20.0,
        )
    )
    db_session.commit()
    response = app_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["cpu_percent"] == 42.0
    assert data["cpu_temp_c"] == 50.0
```

- [ ] **Step 2: Run the new tests**

```bash
uv run pytest tests/dashboard/test_routes.py -v
```
Expected: `7 passed` (5 existing + 2 new)

- [ ] **Step 3: Run the full suite**

```bash
uv run pytest -q
```
Expected: `42 passed`

- [ ] **Step 4: Commit**

```bash
git add tests/dashboard/test_routes.py
git commit -m "test: add dashboard route tests with data in DB"
```

---

## Task 8: Add missing onewire error path tests

**Files:**
- Modify: `tests/sensors/test_onewire.py`

Two code paths in `onewire.py` are never hit: the `OSError` handler (lines 42–52) and the `IndexError/ValueError` parse handler (lines 69–78).

- [ ] **Step 1: Append the two missing tests to `tests/sensors/test_onewire.py`**

Add this import at the top of the file (alongside existing imports):

```python
from unittest.mock import patch
```

Then append at the bottom of the `TestOneWireSensorBusReader` class:

```python
    def test_bus_fault_on_read_oserror(self, tmp_path):
        _write_sensor_file(tmp_path, "28-abc123", "some content")
        reader = _make_reader(tmp_path)
        with patch("pathlib.Path.read_text", side_effect=OSError("bus glitch")):
            readings = reader.read_all([_sensor()])
        assert readings[0].read_quality == ReadQuality.BUS_FAULT
        assert readings[0].temperature_c is None
        assert "bus glitch" in (readings[0].error_message or "")

    def test_parse_failure_returns_bus_fault(self, tmp_path):
        _write_sensor_file(
            tmp_path,
            "28-abc123",
            "xx : crc=xx YES\nno_t_token_here\n",
        )
        reader = _make_reader(tmp_path)
        readings = reader.read_all([_sensor()])
        assert readings[0].read_quality == ReadQuality.BUS_FAULT
        assert readings[0].temperature_c is None
```

- [ ] **Step 2: Run the new tests**

```bash
uv run pytest tests/sensors/test_onewire.py -v
```
Expected: `8 passed` (6 existing + 2 new)

- [ ] **Step 3: Run the full suite**

```bash
uv run pytest -q
```
Expected: `44 passed`

- [ ] **Step 4: Run type checking and linting**

```bash
uv run mypy src/ice_gateway --strict --no-error-summary
```
Expected: `Success: no issues found`

```bash
uv run ruff check src/ tests/
```
Expected: exit 0 (no violations)

- [ ] **Step 5: Commit**

```bash
git add tests/sensors/test_onewire.py
git commit -m "test: add BUS_FAULT OSError and parse-failure tests for onewire reader"
```

---

## Done

After all 8 tasks:
- `PiHealthProvider` ABC injected everywhere; no `patch()` on hardware internals
- `FakeUPS`, `FakeGPIO`, `FakeKSBUNTransport` stub fakes exist in conftest for Phase 2
- `polling_loop` exception-swallowing covered by async test
- Dashboard routes tested with real data
- All onewire error paths covered
- `DateTime(timezone=True)` on both DB timestamp columns
- `mypy --strict` and `ruff check` both exit 0
- 44 tests passing (up from 35)
