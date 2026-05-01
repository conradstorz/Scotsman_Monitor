from unittest.mock import MagicMock, patch

from ice_gateway.sensors.pi_health import read_pi_health

_PSUTIL_PATCHES = {
    "ice_gateway.sensors.pi_health.psutil.cpu_percent": 12.5,
    "ice_gateway.sensors.pi_health.psutil.virtual_memory": MagicMock(
        return_value=MagicMock(percent=44.0)
    ),
    "ice_gateway.sensors.pi_health.psutil.disk_usage": MagicMock(
        return_value=MagicMock(percent=18.0)
    ),
}


class TestReadPiHealth:
    def test_returns_pi_health_object(self, tmp_path):
        temp_file = tmp_path / "temp"
        temp_file.write_text("52000\n")
        with (
            patch("ice_gateway.sensors.pi_health._CPU_TEMP_PATH", temp_file),
            patch(
                "ice_gateway.sensors.pi_health.psutil.cpu_percent",
                return_value=12.5,
            ),
            patch(
                "ice_gateway.sensors.pi_health.psutil.virtual_memory",
                return_value=MagicMock(percent=44.0),
            ),
            patch(
                "ice_gateway.sensors.pi_health.psutil.disk_usage",
                return_value=MagicMock(percent=18.0),
            ),
        ):
            result = read_pi_health()
        assert result.cpu_percent == 12.5
        assert result.memory_percent == 44.0
        assert result.disk_percent == 18.0
        assert result.cpu_temp_c == 52.0
        assert result.timestamp is not None

    def test_cpu_temp_none_when_file_missing(self, tmp_path):
        missing = tmp_path / "nonexistent"
        with (
            patch("ice_gateway.sensors.pi_health._CPU_TEMP_PATH", missing),
            patch(
                "ice_gateway.sensors.pi_health.psutil.cpu_percent",
                return_value=5.0,
            ),
            patch(
                "ice_gateway.sensors.pi_health.psutil.virtual_memory",
                return_value=MagicMock(percent=30.0),
            ),
            patch(
                "ice_gateway.sensors.pi_health.psutil.disk_usage",
                return_value=MagicMock(percent=10.0),
            ),
        ):
            result = read_pi_health()
        assert result.cpu_temp_c is None

    def test_cpu_temp_parsed_correctly(self, tmp_path):
        temp_file = tmp_path / "temp"
        temp_file.write_text("52340\n")
        with (
            patch("ice_gateway.sensors.pi_health._CPU_TEMP_PATH", temp_file),
            patch(
                "ice_gateway.sensors.pi_health.psutil.cpu_percent",
                return_value=5.0,
            ),
            patch(
                "ice_gateway.sensors.pi_health.psutil.virtual_memory",
                return_value=MagicMock(percent=30.0),
            ),
            patch(
                "ice_gateway.sensors.pi_health.psutil.disk_usage",
                return_value=MagicMock(percent=10.0),
            ),
        ):
            result = read_pi_health()
        assert result.cpu_temp_c == 52.34
