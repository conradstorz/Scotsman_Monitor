from typing import Any, ClassVar, Tuple, Type
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource
from pydantic_settings.utils import path_type_label
try:
    from pydantic_settings import TomlConfigSettingsSource
except ImportError:
    TomlConfigSettingsSource = None  # type: ignore[assignment,misc]

from .models import SensorConfig


class NetworkConfig(BaseSettings):
    ksbu_private_interface: str = "eth0"
    ksbu_gateway_ip: str = "192.168.50.1"


class LoggingConfig(BaseSettings):
    level: str = "INFO"
    retain_days: int = 365


class DashboardConfig(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8080


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        toml_file="config/config.local.toml",
        env_file=".env",
        env_nested_delimiter="__",
        toml_file_encoding="utf-8",
    )

    site_name: str = "Ice Gateway"
    machine_name: str = "Scotsman Prodigy"
    timezone: str = "UTC"
    poll_interval_seconds: int = 30

    network: NetworkConfig = NetworkConfig()
    logging: LoggingConfig = LoggingConfig()
    dashboard: DashboardConfig = DashboardConfig()

    temperature_sensors: list[SensorConfig] = []

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        sources: list[PydanticBaseSettingsSource] = [
            init_settings,
            env_settings,
            dotenv_settings,
        ]
        if TomlConfigSettingsSource is not None:
            sources.append(TomlConfigSettingsSource(settings_cls))
        return tuple(sources)
