from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Float, Integer, String, create_engine
from sqlalchemy.engine import Dialect, Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.types import DateTime, TypeDecorator


class TZDateTime(TypeDecorator[datetime]):
    impl = DateTime
    cache_ok = True

    def __init__(self) -> None:
        super().__init__(timezone=True)

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "ice_gateway.sqlite"


class Base(DeclarativeBase):
    pass


class SensorReadingRow(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(TZDateTime(), nullable=False)
    sensor_id: Mapped[str] = mapped_column(String, nullable=False)
    sensor_name: Mapped[str] = mapped_column(String, nullable=False)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_f: Mapped[float | None] = mapped_column(Float, nullable=True)
    read_quality: Mapped[str] = mapped_column(String, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)


class PiHealthRow(Base):
    __tablename__ = "pi_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(TZDateTime(), nullable=False)
    cpu_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpu_percent: Mapped[float] = mapped_column(Float, nullable=False)
    memory_percent: Mapped[float] = mapped_column(Float, nullable=False)
    disk_percent: Mapped[float] = mapped_column(Float, nullable=False)


def create_db_engine(db_path: Path = DB_PATH) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", echo=False)


def init_db(engine: Engine, db_path: Path = DB_PATH) -> None:
    Base.metadata.create_all(engine)
    if db_path.exists():
        db_path.chmod(0o600)


def get_session(engine: Engine) -> Session:
    return Session(engine)
