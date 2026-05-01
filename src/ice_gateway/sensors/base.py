from abc import ABC, abstractmethod
from ..models import SensorConfig, SensorReading


class SensorBusReader(ABC):
    @abstractmethod
    def read_all(self, sensors: list[SensorConfig]) -> list[SensorReading]:
        """Read all enabled sensors. Never raises — returns error readings on failure."""
        ...
