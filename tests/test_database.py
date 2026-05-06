from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ice_gateway.constants import ReadQuality
from ice_gateway.database import PiHealthRow, SensorReadingRow


def _now() -> datetime:
    return datetime.now(UTC)


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
        assert result.timestamp == ts
