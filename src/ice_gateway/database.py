from pathlib import Path

from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "ice_gateway.sqlite"


class Base(DeclarativeBase):
    pass


class SensorReadingRow(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    sensor_id = Column(String, nullable=False)
    sensor_name = Column(String, nullable=False)
    temperature_c = Column(Float, nullable=True)
    temperature_f = Column(Float, nullable=True)
    read_quality = Column(String, nullable=False)
    error_message = Column(String, nullable=True)


class PiHealthRow(Base):
    __tablename__ = "pi_health"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    cpu_temp_c = Column(Float, nullable=True)
    cpu_percent = Column(Float, nullable=False)
    memory_percent = Column(Float, nullable=False)
    disk_percent = Column(Float, nullable=False)


def create_db_engine(db_path: Path = DB_PATH) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", echo=False)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def get_session(engine: Engine) -> Session:
    return Session(engine)
