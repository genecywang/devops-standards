from openclaw_foundation.models.enums import ResultState
from openclaw_foundation.models.responses import CanonicalResponse
from unittest.mock import Mock

from alert_auto_investigator.assist.contracts import (
    ANALYSIS_RESULT_SUCCESS,
    AnalysisRequestPayload,
    AnalysisResponsePayload,
    AnalysisUsagePayload,
    AssistInvocationResult,
)
from alert_auto_investigator.assist.errors import (
    AnalysisRedactionBlockedError,
    AnalysisSchemaError,
)
from alert_auto_investigator.assist.service import ReadonlyAssistService, build_readonly_assist_service
from alert_auto_investigator.config import InvestigatorConfig
from alert_auto_investigator.models.normalized_alert_event import NormalizedAlertEvent


def _make_event() -> NormalizedAlertEvent:
    return NormalizedAlertEvent(
        schema_version="v1",
        source="alertmanager",
        status="firing",
        environment="dev-tw",
        region_code="ap-east-1",
        alert_name="KubernetesJobFailed",
        alert_key="alertmanager:test-cluster:monitoring:KubernetesJobFailed:nightly-backfill",
        resource_type="job",
        resource_name="nightly-backfill",
        summary="Kubernetes Job failed",
        event_time="2026-04-19T00:00:00Z",
        cluster="test-cluster",
        namespace="monitoring",
    )


def _make_response(
    *,
    redaction_applied: bool = True,
    summary: str = "job nightly-backfill failed: reason=BackoffLimitExceeded",
) -> CanonicalResponse:
    return CanonicalResponse(
        request_id="req-001",
        result_state=ResultState.SUCCESS,
        summary=summary,
        actions_attempted=["get_job_status"],
        redaction_applied=redaction_applied,
        metadata={
            "health_state": "failed",
            "attention_required": True,
            "resource_exists": True,
            "primary_reason": "BackoffLimitExceeded",
        },
    )


class _BackendStub:
    def __init__(self) -> None:
        self.calls: list[AnalysisRequestPayload] = []

    def generate(self, payload: AnalysisRequestPayload) -> AnalysisResponsePayload:
        self.calls.append(payload)
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


class _DictBackendStub:
    def generate(self, payload: AnalysisRequestPayload) -> dict[str, object]:
        return {
            "summary": "partial response",
            "confidence": "low",
        }


def test_readonly_assist_service_skips_when_mode_is_off() -> None:
    backend = _BackendStub()
    service = ReadonlyAssistService(mode="off", backend=backend)

    service.after_investigation(
        _make_event(),
        _make_response(),
        channel="C123",
        thread_ts="111.000",
    )

    assert backend.calls == []


def test_readonly_assist_service_skips_when_mode_is_unknown() -> None:
    backend = _BackendStub()
    service = ReadonlyAssistService(mode="typo", backend=backend)

    result = service.after_investigation(
        _make_event(),
        _make_response(),
        channel="C123",
        thread_ts="111.000",
    )

    assert result is None
    assert backend.calls == []


def test_readonly_assist_service_builds_visible_payload_and_returns_structured_result() -> None:
    backend = _BackendStub()
    service = ReadonlyAssistService(mode="visible", backend=backend)

    result = service.after_investigation(
        _make_event(),
        _make_response(),
        channel="C123",
        thread_ts="111.000",
    )

    assert len(backend.calls) == 1
    assert isinstance(result, AssistInvocationResult)
    assert result.request.analysis_mode == "visible"
    assert result.request.context["channel"] == "C123"
    assert result.request.context["thread_ts"] == "111.000"
    assert result.response.summary == "shadow-mode stub summary"
    assert result.response.result_state == ANALYSIS_RESULT_SUCCESS


def test_readonly_assist_service_builds_shadow_payload_and_returns_structured_result() -> None:
    backend = _BackendStub()
    service = ReadonlyAssistService(mode="shadow", backend=backend)

    result = service.after_investigation(
        _make_event(),
        _make_response(),
        channel="C123",
        thread_ts="111.000",
    )

    assert len(backend.calls) == 1
    payload = backend.calls[0]
    assert isinstance(result, AssistInvocationResult)
    assert isinstance(result.request, AnalysisRequestPayload)
    assert isinstance(result.response, AnalysisResponsePayload)
    assert result.request.alert["alert_key"] == "alertmanager:test-cluster:monitoring:KubernetesJobFailed:nightly-backfill"
    assert result.request.investigation["check"] == "get_job_status"
    assert result.request.investigation["metadata"]["primary_reason"] == "BackoffLimitExceeded"
    assert result.request.context["channel"] == "C123"
    assert result.request.context["thread_ts"] == "111.000"
    assert result.response.summary == "shadow-mode stub summary"
    assert result.response.result_state == ANALYSIS_RESULT_SUCCESS


def test_readonly_assist_service_logs_shadow_invocation_and_completion(caplog) -> None:
    backend = _BackendStub()
    service = ReadonlyAssistService(mode="shadow", backend=backend)

    with caplog.at_level("INFO"):
        service.after_investigation(
            _make_event(),
            _make_response(),
            channel="C123",
            thread_ts="111.000",
        )

    assert "assist_shadow_invoked alert_key=alertmanager:test-cluster:monitoring:KubernetesJobFailed:nightly-backfill" in caplog.text
    assert "assist_shadow_completed alert_key=alertmanager:test-cluster:monitoring:KubernetesJobFailed:nightly-backfill" in caplog.text
    assert "confidence=low" in caplog.text


def test_readonly_assist_service_raises_when_dict_response_missing_required_fields() -> None:
    backend = _DictBackendStub()
    service = ReadonlyAssistService(mode="shadow", backend=backend)

    try:
        service.after_investigation(
            _make_event(),
            _make_response(),
            channel="C123",
            thread_ts="111.000",
        )
    except AnalysisSchemaError as exc:
        assert "missing required" in str(exc)
    else:
        raise AssertionError("AnalysisSchemaError was not raised")


def test_readonly_assist_service_blocks_when_redaction_is_not_applied() -> None:
    backend = _BackendStub()
    service = ReadonlyAssistService(mode="shadow", backend=backend)

    try:
        service.after_investigation(
            _make_event(),
            _make_response(redaction_applied=False),
            channel="C123",
            thread_ts="111.000",
        )
    except AnalysisRedactionBlockedError:
        assert backend.calls == []
    else:
        raise AssertionError("AnalysisRedactionBlockedError was not raised")


def test_readonly_assist_service_blocks_when_payload_exceeds_input_ceiling() -> None:
    backend = _BackendStub()
    service = ReadonlyAssistService(mode="shadow", backend=backend)

    try:
        service.after_investigation(
            _make_event(),
            _make_response(summary="x" * 4001),
            channel="C123",
            thread_ts="111.000",
        )
    except AnalysisRedactionBlockedError:
        assert backend.calls == []
    else:
        raise AssertionError("AnalysisRedactionBlockedError was not raised")


def test_build_readonly_assist_service_uses_anthropic_backend_when_configured(monkeypatch) -> None:
    sentinel_client = object()
    sentinel_backend = object()
    build_client_mock = Mock(return_value=sentinel_client)
    backend_ctor_calls: list[dict[str, object]] = []

    def _anthropic_backend_ctor(*, client, model: str, timeout_seconds: float):
        backend_ctor_calls.append(
            {
                "client": client,
                "model": model,
                "timeout_seconds": timeout_seconds,
            }
        )
        return sentinel_backend

    monkeypatch.setattr(
        "alert_auto_investigator.assist.service.build_anthropic_client",
        build_client_mock,
    )
    monkeypatch.setattr(
        "alert_auto_investigator.assist.service.AnthropicReadonlyAssistBackend",
        _anthropic_backend_ctor,
    )

    config = InvestigatorConfig(
        slack_bot_token="xoxb-test",
        slack_app_token="xapp-test",
        region_code="ap-east-1",
        fallback_environment="dev",
        owned_environments=["dev"],
        cooldown_seconds=300,
        rate_limit_count=10,
        rate_limit_window_seconds=3600,
        investigate_allowlist=[],
        investigate_denylist=[],
        assist_provider="anthropic",
        assist_model="claude-3-7-sonnet",
        assist_timeout_seconds=12.5,
    )

    service = build_readonly_assist_service(config)

    assert service._backend is sentinel_backend
    build_client_mock.assert_called_once_with()
    assert backend_ctor_calls == [
        {
            "client": sentinel_client,
            "model": "claude-3-7-sonnet",
            "timeout_seconds": 12.5,
        }
    ]


def test_build_readonly_assist_service_keeps_stub_backend_when_provider_is_stub() -> None:
    config = InvestigatorConfig(
        slack_bot_token="xoxb-test",
        slack_app_token="xapp-test",
        region_code="ap-east-1",
        fallback_environment="dev",
        owned_environments=["dev"],
        cooldown_seconds=300,
        rate_limit_count=10,
        rate_limit_window_seconds=3600,
        investigate_allowlist=[],
        investigate_denylist=[],
        assist_provider="stub",
    )

    service = build_readonly_assist_service(config)

    assert service._backend.__class__.__name__ == "StubReadonlyAssistBackend"


def test_from_env_parses_assist_model(monkeypatch) -> None:
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")
    monkeypatch.setenv("REGION_CODE", "ap-east-1")
    monkeypatch.setenv("FALLBACK_ENVIRONMENT", "dev")
    monkeypatch.setenv("OWNED_ENVIRONMENTS", "dev")
    monkeypatch.setenv("OPENCLAW_READONLY_ASSIST_MODEL", "claude-3-7-sonnet")

    config = InvestigatorConfig.from_env()

    assert config.assist_model == "claude-3-7-sonnet"
