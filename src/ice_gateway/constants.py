from enum import Enum


class ReadQuality(str, Enum):
    OK = "ok"
    CRC_ERROR = "crc_error"
    IMPOSSIBLE_VALUE = "impossible_value"
    MISSING = "missing"
    BUS_FAULT = "bus_fault"
