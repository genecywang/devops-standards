from openclaw_foundation.models.enums import ResultState
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import CanonicalResponse
from openclaw_foundation.runtime.state_machine import RuntimeState
from openclaw_foundation.tools.registry import ToolRegistry


class OpenClawRunner:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry
        self.state_history: list[RuntimeState] = []

    def _transition(self, state: RuntimeState) -> None:
        self.state_history.append(state)

    def _response(
        self,
        request: InvestigationRequest,
        result_state: ResultState,
        summary: str,
        actions_attempted: list[str],
    ) -> CanonicalResponse:
        return CanonicalResponse(
            request_id=request.request_id,
            result_state=result_state,
            summary=summary,
            actions_attempted=actions_attempted,
            redaction_applied=True,
        )

    def run(self, request: InvestigationRequest) -> CanonicalResponse:
        self.state_history = [RuntimeState.RECEIVED, RuntimeState.VALIDATED]

        if request.budget.max_tool_calls <= 0:
            return self._response(
                request,
                ResultState.FALLBACK,
                "budget exhausted before tool execution",
                [],
            )

        try:
            tool = self._registry.get("fake_investigation")
        except KeyError:
            return self._response(
                request,
                ResultState.FAILED,
                "no registered tool available for investigation",
                [],
            )

        self._transition(RuntimeState.EXECUTING)
        tool_result = tool.invoke(request)
        self._transition(RuntimeState.REDACTING)
        self._transition(RuntimeState.COMPLETED)
        return self._response(
            request,
            ResultState.SUCCESS,
            tool_result.summary,
            [tool.tool_name],
        )
