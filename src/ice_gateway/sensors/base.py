from abc import ABC, abstractmethod

from ..models import PiHealth, SensorConfig, SensorReading


class SensorBusReader(ABC):
    @abstractmethod
    def read_all(self, sensors: list[SensorConfig]) -> list[SensorReading]:
        """Read all enabled sensors. Returns error readings on failure, never raises."""
        ...


class PiHealthProvider(ABC):
    @abstractmethod
    def read(self) -> PiHealth:
        ...


class UPSStatusProvider(ABC):
    pass


class KSBUNTransport(ABC):
    pass


class GPIOController(ABC):
    pass
