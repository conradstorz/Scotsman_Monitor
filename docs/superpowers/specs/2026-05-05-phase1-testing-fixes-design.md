# Phase 1 Testing Fixes — Design Spec

**Date:** 2026-05-05
**Scope:** Fix all Critical and Important issues identified in the Phase 1 code review, with emphasis on hardware abstraction and test coverage.

---

## Context

A code review of the Phase 1 implementation found two Critical and six Important issues, all related to the hardware abstraction rule and test coverage gaps. This spec defines the changes needed before Phase 2 work begins.

**Core rule (from CLAUDE.md):** Every hardware boundary must have an ABC that production code depends on via constructor injection — not import-time globals.

---

## Group A — Structural Fixes

### 1. `PiHealthProvider` ABC

Add to `src/ice_gateway/sensors/base.py`:

```python
class PiHealthProvider(ABC):
    @abstractmethod
    def read(self) -> PiHealth: ...
```

Rename and restructure `src/ice_gateway/sensors/pi_health.py`:
- Remove the bare `read_pi_health()` module-level function
- Add `_DEFAULT_CPU_TEMP_PATH = Path("/sys/class/thermal/thermal_zone0/temp")`
- Add `PsutilPiHealthProvider(cpu_temp_path: Path = _DEFAULT_CPU_TEMP_PATH)` implementing `PiHealthProvider`
- Constructor accepts `cpu_temp_path` so tests can inject a `tmp_path` file without any patching

This mirrors the `SensorBusReader` / `OneWireSensorBusReader` pattern exactly.

### 2. Inject `PiHealthProvider` into polling

Change `_poll_once` signature:
```python
def _poll_once(
    config: AppConfig,
    engine: Engine,
    sensor_bus: SensorBusReader,
    pi_health_provider: PiHealthProvider,
) -> None:
```

Change `polling_loop` signature to accept and pass through `pi_health_provider`.

`main._run` constructs both concrete providers and passes them:
```python
async def _run(config: AppConfig, engine: Engine) -> None:
    sensor_bus = OneWireSensorBusReader()
    pi_health_provider = PsutilPiHealthProvider()
    ...
    await asyncio.gather(
        polling_loop(config, engine, sensor_bus, pi_health_provider),
        server.serve(),
    )
```

### 3. Stub ABCs for Phase 2 interfaces

Add to `src/ice_gateway/sensors/base.py` as abstract stubs (no methods yet — interfaces only):

```python
class UPSStatusProvider(ABC): ...
class KSBUNTransport(ABC): ...
class GPIOController(ABC): ...
```

These exist so Phase 2 can add methods and fakes without retrofitting injection.

### 4. Update `conftest.py`

Add to `tests/conftest.py`:

```python
class FakePiHealthProvider(PiHealthProvider):
    def __init__(self, result: PiHealth) -> None: ...
    def read(self) -> PiHealth: return self._result

class FakeUPS(UPSStatusProvider): pass
class FakeGPIO(GPIOController): pass
class FakeKSBUNTransport(KSBUNTransport): pass
```

Add `fake_pi_health_provider` fixture returning a `FakePiHealthProvider` with a sensible default `PiHealth`.

### 5. Rewrite `test_pi_health.py`

Replace all `patch()` calls with direct construction:

```python
def test_returns_pi_health_object(tmp_path):
    temp_file = tmp_path / "temp"
    temp_file.write_text("52000\n")
    provider = PsutilPiHealthProvider(cpu_temp_path=temp_file)
    result = provider.read()
    assert result.cpu_temp_c == pytest.approx(52.0)

def test_cpu_temp_none_when_file_missing(tmp_path):
    provider = PsutilPiHealthProvider(cpu_temp_path=tmp_path / "nonexistent")
    result = provider.read()
    assert result.cpu_temp_c is None
```

`cpu_percent`, `memory_percent`, `disk_percent` still come from real `psutil` — that is acceptable since they don't touch hardware files on the test machine. The only injected dependency is `cpu_temp_path`.

Update `test_polling.py` to pass `fake_pi_health_provider` into `_poll_once` instead of using `patch("ice_gateway.tasks.polling.read_pi_health", ...)`.

---

## Group B — Data & Test Coverage Fixes

### 6. `DateTime(timezone=True)` in `database.py`

Change both column definitions:
```python
timestamp = Column(DateTime(timezone=True), nullable=False)
```

Applies to `SensorReadingRow` and `PiHealthRow`.

Add a round-trip test in `test_database.py`:
- Insert a row with a timezone-aware `datetime`
- Read it back
- Assert `row.timestamp.tzinfo is not None`

### 7. `polling_loop` exception-swallowing test

Add an async test in `test_polling.py` that:
1. Creates a `FakePiHealthProvider` whose `read()` raises `RuntimeError` on the first call, then returns a valid `PiHealth` on subsequent calls
2. Patches `asyncio.sleep` with a `side_effect` counter that raises `asyncio.CancelledError` after 2 calls (stopping the loop)
3. Calls `await polling_loop(...)` inside `pytest.raises(asyncio.CancelledError)` — `CancelledError` is a `BaseException` and escapes the `except Exception` handler cleanly
4. Asserts the second iteration wrote a `PiHealthRow` to the DB

This verifies that `except Exception` in `polling_loop` swallows crashes without killing the loop.

### 8. Dashboard tests with data

Add two tests to `tests/dashboard/test_routes.py` that receive both `app_client` and `db_session` (they share the same `db_engine` fixture, so data inserted via the session is visible to the app):

```python
def test_api_temperatures_returns_data(app_client, db_session):
    db_session.add(SensorReadingRow(sensor_id="28-abc", ...))
    db_session.commit()
    response = app_client.get("/api/temperatures")
    assert response.json()[0]["sensor_id"] == "28-abc"

def test_api_health_returns_data(app_client, db_session):
    db_session.add(PiHealthRow(cpu_percent=42.0, ...))
    db_session.commit()
    response = app_client.get("/api/health")
    assert response.json()["cpu_percent"] == 42.0
```

### 9. Onewire missing error paths

Add two tests to `tests/sensors/test_onewire.py`:

**OSError → BUS_FAULT:**
```python
def test_bus_fault_on_read_error(tmp_path):
    _write_sensor_file(tmp_path, "28-abc123", "content")
    reader = _make_reader(tmp_path)
    with patch("pathlib.Path.read_text", side_effect=OSError("bus glitch")):
        readings = reader.read_all([_sensor()])
    assert readings[0].read_quality == ReadQuality.BUS_FAULT
```

**No `t=` token → BUS_FAULT (parse IndexError):**
```python
def test_parse_failure_returns_bus_fault(tmp_path):
    _write_sensor_file(
        tmp_path, "28-abc123",
        "xx : crc=xx YES\nno_t_token_here\n",
    )
    reader = _make_reader(tmp_path)
    readings = reader.read_all([_sensor()])
    assert readings[0].read_quality == ReadQuality.BUS_FAULT
```

---

## Files Changed

| File | Change |
|---|---|
| `src/ice_gateway/sensors/base.py` | Add `PiHealthProvider`, `UPSStatusProvider`, `KSBUNTransport`, `GPIOController` ABCs |
| `src/ice_gateway/sensors/pi_health.py` | Replace function with `PsutilPiHealthProvider` class |
| `src/ice_gateway/tasks/polling.py` | Inject `PiHealthProvider`; add it to `_poll_once` and `polling_loop` |
| `src/ice_gateway/main.py` | Construct `PsutilPiHealthProvider`, pass to `polling_loop` |
| `src/ice_gateway/database.py` | Add `timezone=True` to both `DateTime` columns |
| `tests/conftest.py` | Add `FakePiHealthProvider`, `FakeUPS`, `FakeGPIO`, `FakeKSBUNTransport` and fixture |
| `tests/sensors/test_pi_health.py` | Rewrite using constructor injection, no `patch()` |
| `tests/tasks/test_polling.py` | Use `fake_pi_health_provider`; add `polling_loop` exception test |
| `tests/dashboard/test_routes.py` | Add two tests with data in DB |
| `tests/sensors/test_onewire.py` | Add OSError and parse-failure tests |
| `tests/test_database.py` | Add `timezone` round-trip test |

---

## Success Criteria

- All existing 35 tests continue to pass
- No `patch()` calls remain in `test_pi_health.py`
- `polling_loop` exception-swallowing is covered by an async test
- Dashboard routes are tested with real data in the DB
- Both previously-uncovered onewire error paths are hit
- `DateTime` columns use `timezone=True`
- `FakeUPS`, `FakeGPIO`, `FakeKSBUNTransport` exist in `conftest.py`
- `mypy --strict` still passes on `src/`
- `ruff check` exits 0
