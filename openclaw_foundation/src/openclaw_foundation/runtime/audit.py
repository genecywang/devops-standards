from dataclasses import dataclass


@dataclass(slots=True)
class AuditEvent:
    request_id: str
    tool_name: str
    cluster: str
    namespace: str
    result_state: str
    error_reason: str | None = None
