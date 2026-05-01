from unittest.mock import patch

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
