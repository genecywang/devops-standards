from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.runtime.runner import OpenClawRunner
from openclaw_foundation.runtime.state_machine import RuntimeState
from openclaw_foundation.tools.fake_investigation import FakeInvestigationTool
from openclaw_foundation.tools.registry import ToolRegistry


def make_request() -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-001",
        source_product="alert_auto_investigator",
        scope={"environment": "staging", "cluster": "staging-main"},
        input_ref="fixture:demo",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=30,
            max_output_tokens=256,
        ),
    )


def test_registry_returns_registered_tool() -> None:
    registry = ToolRegistry()
    tool = FakeInvestigationTool()

    registry.register(tool)

    assert registry.get("fake_investigation") is tool


def test_fake_tool_returns_summary_and_evidence() -> None:
    tool = FakeInvestigationTool()

    result = tool.invoke(make_request())

    assert "req-001" in result.summary
    assert result.evidence == ["input_ref=fixture:demo"]


def test_runner_success_path() -> None:
    registry = ToolRegistry()
    registry.register(FakeInvestigationTool())
    runner = OpenClawRunner(registry)

    response = runner.run(make_request())

    assert response.request_id == "req-001"
    assert response.result_state == "success"
    assert response.actions_attempted == ["fake_investigation"]
    assert response.redaction_applied is True
    assert runner.state_history == [
        RuntimeState.RECEIVED,
        RuntimeState.VALIDATED,
        RuntimeState.EXECUTING,
        RuntimeState.REDACTING,
        RuntimeState.COMPLETED,
    ]


def test_runner_missing_tool_returns_failed() -> None:
    runner = OpenClawRunner(ToolRegistry())

    response = runner.run(make_request())

    assert response.result_state == "failed"
    assert response.actions_attempted == []


def test_runner_budget_exceeded_returns_fallback() -> None:
    registry = ToolRegistry()
    registry.register(FakeInvestigationTool())
    runner = OpenClawRunner(registry)
    request = make_request()
    request.budget.max_tool_calls = 0

    response = runner.run(request)

    assert response.result_state == "fallback"
