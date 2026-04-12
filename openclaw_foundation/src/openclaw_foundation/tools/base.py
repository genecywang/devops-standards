from typing import Protocol

from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult


class InvestigationTool(Protocol):
    tool_name: str
    supported_request_types: tuple[str, ...]

    def invoke(self, request: InvestigationRequest) -> ToolResult: ...
