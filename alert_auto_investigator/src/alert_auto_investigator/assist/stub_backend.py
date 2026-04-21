from __future__ import annotations

from alert_auto_investigator.assist.contracts import (
    ANALYSIS_RESULT_SUCCESS,
    AnalysisRequestPayload,
    AnalysisResponsePayload,
    AnalysisUsagePayload,
)


class StubReadonlyAssistBackend:
    def generate(self, payload: AnalysisRequestPayload) -> AnalysisResponsePayload:
        return AnalysisResponsePayload(
            summary="shadow-mode stub summary",
            current_interpretation="shadow-mode stub interpretation",
            recommended_next_step="no action; stub backend only",
            confidence="low",
            caveats=["stub backend"],
            provider="stub",
            model="stub-v1",
            prompt_version=payload.prompt_version,
            output_schema_version=payload.output_schema_version,
            usage=AnalysisUsagePayload(input_tokens=0, output_tokens=0, latency_ms=0),
            result_state=ANALYSIS_RESULT_SUCCESS,
        )
