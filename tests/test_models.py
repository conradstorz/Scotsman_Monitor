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
