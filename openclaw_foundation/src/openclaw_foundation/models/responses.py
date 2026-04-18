from dataclasses import dataclass, field

from openclaw_foundation.models.enums import ResultState


@dataclass(slots=True)
class ToolResult:
    summary: str
    evidence: list[dict[str, object]] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class CanonicalResponse:
    request_id: str
    result_state: ResultState
    summary: str
    actions_attempted: list[str]
    redaction_applied: bool
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("request_id is required")
        if not self.summary:
            raise ValueError("summary is required")
