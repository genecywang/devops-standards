from openclaw_foundation.models.enums import RequestType, ResultState
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.models.responses import CanonicalResponse


def test_budget_fields_round_trip() -> None:
    budget = ExecutionBudget(
        max_steps=1,
        max_tool_calls=1,
        max_duration_seconds=10,
        max_output_tokens=100,
    )

    assert budget.max_steps == 1
    assert budget.max_tool_calls == 1
    assert budget.max_duration_seconds == 10
    assert budget.max_output_tokens == 100


def test_investigation_request_preserves_fields() -> None:
    request = InvestigationRequest(
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

    assert request.request_id == "req-001"
    assert request.scope["environment"] == "staging"


def test_canonical_response_uses_result_state() -> None:
    response = CanonicalResponse(
        request_id="req-001",
        result_state=ResultState.SUCCESS,
        summary="ok",
        actions_attempted=["fake_investigation"],
        redaction_applied=True,
    )

    assert response.result_state == ResultState.SUCCESS
