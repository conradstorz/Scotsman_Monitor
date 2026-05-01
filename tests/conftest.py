import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from ice_gateway.dashboard.app import create_app
from ice_gateway.database import Base, init_db
from ice_gateway.models import SensorConfig, SensorReading
from ice_gateway.sensors.base import SensorBusReader


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


@pytest.fixture
def app_client(db_engine):
    app = create_app(db_engine)
    with TestClient(app) as client:
        yield client
