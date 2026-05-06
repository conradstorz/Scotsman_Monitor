from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from ice_gateway.dashboard.app import create_app
from ice_gateway.database import Base, init_db
from ice_gateway.models import PiHealth, SensorConfig, SensorReading
from ice_gateway.sensors.base import (
    GPIOController,
    KSBUNTransport,
    PiHealthProvider,
    SensorBusReader,
    UPSStatusProvider,
)

_DEFAULT_FAKE_HEALTH = PiHealth(
    cpu_temp_c=45.0,
    cpu_percent=10.0,
    memory_percent=40.0,
    disk_percent=20.0,
    timestamp=datetime(2024, 1, 1, tzinfo=UTC),
)


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    with Session(db_engine) as session:
        yield session


class FakeSensorBus(SensorBusReader):
    def __init__(self, readings: list[SensorReading]) -> None:
        self._readings = readings

    def read_all(self, sensors: list[SensorConfig]) -> list[SensorReading]:
        return self._readings


@pytest.fixture
def fake_sensor_bus():
    def factory(readings: list[SensorReading]) -> FakeSensorBus:
        return FakeSensorBus(readings)

    return factory


class FakePiHealthProvider(PiHealthProvider):
    def __init__(self, result: PiHealth = _DEFAULT_FAKE_HEALTH) -> None:
        self._result = result

    def read(self) -> PiHealth:
        return self._result


class FakeUPS(UPSStatusProvider):  # noqa: B024
    pass


class FakeGPIO(GPIOController):  # noqa: B024
    pass


class FakeKSBUNTransport(KSBUNTransport):  # noqa: B024
    pass


@pytest.fixture
def fake_pi_health_provider() -> FakePiHealthProvider:
    return FakePiHealthProvider()


@pytest.fixture
def app_client(db_engine):
    app = create_app(db_engine)
    with TestClient(app) as client:
        yield client
