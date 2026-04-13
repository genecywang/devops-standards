from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult


class FakeInvestigationTool:
    tool_name = "fake_investigation"
    supported_request_types = ("investigation",)

    def invoke(self, request: InvestigationRequest) -> ToolResult:
        return ToolResult(
            summary=f"fake investigation completed for {request.request_id}",
            evidence=[{"input_ref": request.input_ref}],
        )
