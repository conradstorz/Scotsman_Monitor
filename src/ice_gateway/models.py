from datetime import datetime
from pydantic import BaseModel
from .constants import ReadQuality


class SensorConfig(BaseModel):
    id: str
    name: str
    location: str
    enabled: bool = True
    alert_min_f: float | None = None
    alert_max_f: float | None = None


class SensorReading(BaseModel):
    sensor_id: str
    sensor_name: str
    temperature_c: float | None
    temperature_f: float | None
    read_quality: ReadQuality
    error_message: str | None = None
    timestamp: datetime


class PiHealth(BaseModel):
    cpu_temp_c: float | None
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    timestamp: datetime
