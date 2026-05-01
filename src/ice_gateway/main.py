import asyncio

import uvicorn
from loguru import logger
from sqlalchemy.engine import Engine

from .config import AppConfig
from .dashboard.app import create_app
from .database import create_db_engine, init_db
from .logging_setup import configure_logging
from .sensors.onewire import OneWireSensorBusReader
from .tasks.polling import polling_loop


def main() -> None:
    config = AppConfig()
    configure_logging(config.logging.level, config.logging.retain_days)
    logger.info("Starting Ice Gateway — site={site}", site=config.site_name)

    engine = create_db_engine()
    init_db(engine)
    logger.info("Database ready")

    asyncio.run(_run(config, engine))


async def _run(config: AppConfig, engine: Engine) -> None:
    sensor_bus = OneWireSensorBusReader()
    app = create_app(engine)

    server = uvicorn.Server(
        uvicorn.Config(
            app=app,
            host=config.dashboard.host,
            port=config.dashboard.port,
            log_level="warning",
        )
    )

    await asyncio.gather(
        polling_loop(config, engine, sensor_bus),
        server.serve(),
    )
