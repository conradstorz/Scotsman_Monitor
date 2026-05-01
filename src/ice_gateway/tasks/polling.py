import asyncio

from loguru import logger
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ..config import AppConfig
from ..database import PiHealthRow, SensorReadingRow
from ..sensors.base import SensorBusReader
from ..sensors.pi_health import read_pi_health


async def polling_loop(
    config: AppConfig, engine: Engine, sensor_bus: SensorBusReader
) -> None:
    logger.info(
        "Polling loop started — interval={interval}s, sensors={count}",
        interval=config.poll_interval_seconds,
        count=len(config.temperature_sensors),
    )
    while True:
        try:
            _poll_once(config, engine, sensor_bus)
        except Exception:
            logger.exception("Unexpected error in polling loop")
        await asyncio.sleep(config.poll_interval_seconds)


def _poll_once(config: AppConfig, engine: Engine, sensor_bus: SensorBusReader) -> None:
    readings = sensor_bus.read_all(config.temperature_sensors)
    health = read_pi_health()

    with Session(engine) as session:
        for r in readings:
            session.add(
                SensorReadingRow(
                    timestamp=r.timestamp,
                    sensor_id=r.sensor_id,
                    sensor_name=r.sensor_name,
                    temperature_c=r.temperature_c,
                    temperature_f=r.temperature_f,
                    read_quality=r.read_quality.value,
                    error_message=r.error_message,
                )
            )
        session.add(
            PiHealthRow(
                timestamp=health.timestamp,
                cpu_temp_c=health.cpu_temp_c,
                cpu_percent=health.cpu_percent,
                memory_percent=health.memory_percent,
                disk_percent=health.disk_percent,
            )
        )
        session.commit()

    logger.info(
        "Poll complete — {count} sensor reading(s) written", count=len(readings)
    )
