from __future__ import annotations

from dataclasses import dataclass, field


ANALYSIS_RESULT_SUCCESS = "success"
ANALYSIS_RESULT_SCHEMA_ERROR = "schema_error"
ANALYSIS_RESULT_TIMEOUT = "timeout"
ANALYSIS_RESULT_RATE_LIMIT = "rate_limit"
ANALYSIS_RESULT_PROVIDER_ERROR = "provider_error"
ANALYSIS_RESULT_REDACTION_BLOCKED = "redaction_blocked"


@dataclass(slots=True)
class AnalysisUsagePayload:
    input_tokens: int
    output_tokens: int
    latency_ms: int


@dataclass(slots=True)
class AnalysisRequestPayload:
    alert: dict[str, object]
    investigation: dict[str, object]
    context: dict[str, object]
    prompt_version: str
    output_schema_version: str
    analysis_mode: str
    max_input_tokens: int
    max_output_tokens: int


@dataclass(slots=True)
class AnalysisResponsePayload:
    summary: str
    current_interpretation: str
    recommended_next_step: str
    confidence: str
    caveats: list[str] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    prompt_version: str = "analysis-v1"
    output_schema_version: str = "v1"
    usage: AnalysisUsagePayload | None = None
    result_state: str = ANALYSIS_RESULT_SUCCESS

    def __post_init__(self) -> None:
        if not self.summary:
            raise ValueError("summary is required")
        if not self.current_interpretation:
            raise ValueError("current_interpretation is required")
        if not self.recommended_next_step:
            raise ValueError("recommended_next_step is required")
        if not self.confidence:
            raise ValueError("confidence is required")


@dataclass(slots=True)
class AssistInvocationResult:
    request: AnalysisRequestPayload
    response: AnalysisResponsePayload
