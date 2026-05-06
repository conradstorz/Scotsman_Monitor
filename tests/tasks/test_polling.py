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
