from datetime import UTC, datetime
from pathlib import Path

import psutil
from loguru import logger

from ..models import PiHealth
from .base import PiHealthProvider

_DEFAULT_CPU_TEMP_PATH = Path("/sys/class/thermal/thermal_zone0/temp")


class PsutilPiHealthProvider(PiHealthProvider):
    def __init__(self, cpu_temp_path: Path = _DEFAULT_CPU_TEMP_PATH) -> None:
        self._cpu_temp_path = cpu_temp_path

    def read(self) -> PiHealth:
        now = datetime.now(UTC)

        cpu_temp_c: float | None = None
        try:
            cpu_temp_c = int(self._cpu_temp_path.read_text().strip()) / 1000.0
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
