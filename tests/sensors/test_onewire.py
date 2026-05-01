from pathlib import Path

import pytest

from ice_gateway.constants import ReadQuality
from ice_gateway.models import SensorConfig
from ice_gateway.sensors.onewire import OneWireSensorBusReader


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
