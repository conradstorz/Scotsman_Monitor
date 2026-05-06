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
