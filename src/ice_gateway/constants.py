from enum import StrEnum


class ReadQuality(StrEnum):
    OK = "ok"
    CRC_ERROR = "crc_error"
    IMPOSSIBLE_VALUE = "impossible_value"
    MISSING = "missing"
    BUS_FAULT = "bus_fault"
