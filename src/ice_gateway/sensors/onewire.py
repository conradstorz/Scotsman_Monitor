from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from ..constants import ReadQuality
from ..models import SensorConfig, SensorReading
from .base import SensorBusReader

_DEFAULT_W1_PATH = Path("/sys/bus/w1/devices")
_TEMP_MIN_C = -55.0
_TEMP_MAX_C = 125.0


class OneWireSensorBusReader(SensorBusReader):
    def __init__(self, w1_devices_path: Path = _DEFAULT_W1_PATH) -> None:
        self._w1_path = w1_devices_path

    def read_all(self, sensors: list[SensorConfig]) -> list[SensorReading]:
        return [self._read(s) for s in sensors if s.enabled]

    def _read(self, sensor: SensorConfig) -> SensorReading:
        now = datetime.now(UTC)
        device_file = self._w1_path / sensor.id / "w1_slave"

        if not device_file.exists():
            logger.warning(
                "Sensor {name} ({id}) not found", name=sensor.name, id=sensor.id
            )
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
            logger.error(
                "Bus fault reading {name}: {exc}", name=sensor.name, exc=exc
            )
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
                "Impossible value from {name}: {temp}°C",
                name=sensor.name,
                temp=temp_c,
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
