from openclaw_foundation.tools.base import InvestigationTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, InvestigationTool] = {}

    def register(self, tool: InvestigationTool) -> None:
        self._tools[tool.tool_name] = tool

    def get(self, tool_name: str) -> InvestigationTool:
        return self._tools[tool_name]
