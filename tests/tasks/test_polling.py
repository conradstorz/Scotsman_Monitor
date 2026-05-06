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


def test_poll_once_writes_sensor_reading(
    config, db_engine, fake_sensor_bus, fake_pi_health_provider
):
    reading = _make_reading()
    bus = fake_sensor_bus([reading])

    _poll_once(config, db_engine, bus, fake_pi_health_provider)

    with Session(db_engine) as session:
        rows = session.execute(select(SensorReadingRow)).scalars().all()
    assert len(rows) == 1
    assert rows[0].sensor_id == "28-abc"
    assert rows[0].temperature_c == 2.5
    assert rows[0].read_quality == "ok"


def test_poll_once_writes_pi_health(
    config, db_engine, fake_sensor_bus, fake_pi_health_provider
):
    bus = fake_sensor_bus([])

    _poll_once(config, db_engine, bus, fake_pi_health_provider)

    with Session(db_engine) as session:
        row = session.execute(select(PiHealthRow)).scalar_one()
    assert row.cpu_temp_c == 45.0
    assert row.cpu_percent == 10.0


def test_poll_once_multiple_readings(
    config, db_engine, fake_sensor_bus, fake_pi_health_provider
):
    readings = [_make_reading("28-aaa"), _make_reading("28-bbb")]
    bus = fake_sensor_bus(readings)

    _poll_once(config, db_engine, bus, fake_pi_health_provider)

    with Session(db_engine) as session:
        rows = session.execute(select(SensorReadingRow)).scalars().all()
    assert len(rows) == 2
    assert {r.sensor_id for r in rows} == {"28-aaa", "28-bbb"}


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
