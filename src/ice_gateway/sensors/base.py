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


class UPSStatusProvider(ABC):  # noqa: B024 — Phase 2 stub, interface TBD
    pass


class KSBUNTransport(ABC):  # noqa: B024 — Phase 2 stub, interface TBD
    pass


class GPIOController(ABC):  # noqa: B024 — Phase 2 stub, interface TBD
    pass
