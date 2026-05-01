import pytest
from sqlalchemy import create_engine
from ice_gateway.database import Base, init_db


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine):
    from sqlalchemy.orm import Session
    with Session(db_engine) as session:
        yield session


from ice_gateway.sensors.base import SensorBusReader
from ice_gateway.models import SensorConfig, SensorReading


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
