import sys
from pathlib import Path
from loguru import logger

LOGS_DIR = Path("logs")


def configure_logging(level: str = "INFO", retain_days: int = 365) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )
    logger.add(
        LOGS_DIR / "ice_gateway.log",
        level=level,
        rotation="1 day",
        retention=f"{retain_days} days",
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
        encoding="utf-8",
    )
    logger.add(
        LOGS_DIR / "sensors.log",
        level=level,
        rotation="1 day",
        retention=f"{retain_days} days",
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
        filter=lambda record: "sensors" in record["name"],
        encoding="utf-8",
    )
