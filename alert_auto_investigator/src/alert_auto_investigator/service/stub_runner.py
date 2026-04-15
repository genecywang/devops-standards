from dataclasses import dataclass


@dataclass
class StubResponse:
    summary: str = "[stub] OpenClaw runner not yet wired — investigation placeholder"


class StubInvestigationRunner:
    """Placeholder runner used before OpenClaw is connected.

    Returns a canned response so the full Slack event → parse → control →
    dispatch → reply pipeline can be exercised end-to-end without a live
    OpenClaw instance.
    """

    def run(self, request: object) -> StubResponse:
        return StubResponse()
