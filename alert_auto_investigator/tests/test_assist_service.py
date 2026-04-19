from openclaw_foundation.models.enums import ResultState
from openclaw_foundation.models.responses import CanonicalResponse

from alert_auto_investigator.assist.service import ReadonlyAssistService
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


def _make_response() -> CanonicalResponse:
    return CanonicalResponse(
        request_id="req-001",
        result_state=ResultState.SUCCESS,
        summary="job nightly-backfill failed: reason=BackoffLimitExceeded",
        actions_attempted=["get_job_status"],
        redaction_applied=True,
        metadata={
            "health_state": "failed",
            "attention_required": True,
            "resource_exists": True,
            "primary_reason": "BackoffLimitExceeded",
        },
    )


class _BackendStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(payload)
        return {
            "operator_assessment": "shadow-mode stub",
            "next_steps": [],
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


def test_readonly_assist_service_builds_shadow_payload_and_calls_backend() -> None:
    backend = _BackendStub()
    service = ReadonlyAssistService(mode="shadow", backend=backend)

    service.after_investigation(
        _make_event(),
        _make_response(),
        channel="C123",
        thread_ts="111.000",
    )

    assert len(backend.calls) == 1
    payload = backend.calls[0]
    assert payload["alert"]["alert_key"] == "alertmanager:test-cluster:monitoring:KubernetesJobFailed:nightly-backfill"
    assert payload["investigation"]["check"] == "get_job_status"
    assert payload["investigation"]["metadata"]["primary_reason"] == "BackoffLimitExceeded"
    assert payload["context"]["channel"] == "C123"
    assert payload["context"]["thread_ts"] == "111.000"
