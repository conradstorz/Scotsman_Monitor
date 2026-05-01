import shutil

import pytest
from pydantic import ValidationError

from ice_gateway.config import AppConfig


def test_config_loads_valid_toml(monkeypatch, tmp_path):
    (tmp_path / "config").mkdir()
    shutil.copy(
        "tests/fixtures/config_valid.toml",
        tmp_path / "config" / "config.local.toml",
    )
    (tmp_path / ".env").write_text("")
    monkeypatch.chdir(tmp_path)
    config = AppConfig()
    assert config.site_name == "Test Location"
    assert config.poll_interval_seconds == 30
    assert len(config.temperature_sensors) == 1
    assert config.temperature_sensors[0].id == "28-test000000"


def test_config_defaults_without_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    config = AppConfig()
    assert config.site_name == "Ice Gateway"
    assert config.poll_interval_seconds == 30


def test_config_sensor_missing_id_raises(monkeypatch, tmp_path):
    (tmp_path / "config").mkdir()
    shutil.copy(
        "tests/fixtures/config_missing_sensor_id.toml",
        tmp_path / "config" / "config.local.toml",
    )
    (tmp_path / ".env").write_text("")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValidationError):
        AppConfig()


def test_config_env_override(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SITE_NAME", "Override Site")
    config = AppConfig()
    assert config.site_name == "Override Site"
