from enum import StrEnum


class RequestType(StrEnum):
    INVESTIGATION = "investigation"


class ResultState(StrEnum):
    SUCCESS = "success"
    DENIED = "denied"
    FAILED = "failed"
    FALLBACK = "fallback"
