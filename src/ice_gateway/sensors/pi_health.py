from datetime import UTC, datetime
from pathlib import Path

import psutil
from loguru import logger

from ..models import PiHealth

_CPU_TEMP_PATH = Path("/sys/class/thermal/thermal_zone0/temp")


def read_pi_health() -> PiHealth:
    now = datetime.now(UTC)

    cpu_temp_c: float | None = None
    try:
        cpu_temp_c = int(_CPU_TEMP_PATH.read_text().strip()) / 1000.0
    except (OSError, ValueError) as exc:
        logger.warning("Could not read CPU temperature: {exc}", exc=exc)

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return PiHealth(
        cpu_temp_c=cpu_temp_c,
        cpu_percent=psutil.cpu_percent(interval=0.1),
        memory_percent=memory.percent,
        disk_percent=disk.percent,
        timestamp=now,
    )
