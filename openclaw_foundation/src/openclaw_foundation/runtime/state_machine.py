from enum import StrEnum


class RuntimeState(StrEnum):
    RECEIVED = "received"
    VALIDATED = "validated"
    EXECUTING = "executing"
    REDACTING = "redacting"
    COMPLETED = "completed"
