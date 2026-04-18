from openclaw_foundation.models.enums import ResultState
from openclaw_foundation.models.responses import CanonicalResponse

from alert_auto_investigator.models.normalized_alert_event import NormalizedAlertEvent
from alert_auto_investigator.service.formatter import format_investigation_reply


def make_event(**overrides) -> NormalizedAlertEvent:
    defaults = dict(
        schema_version="v1",
        source="alertmanager",
        status="firing",
        environment="dev",
        region_code="ap-east-1",
        alert_name="DeploymentReplicasMismatch",
        alert_key="alertmanager:test-cluster:dev:DeploymentReplicasMismatch:medication-service",
        resource_type="deployment",
        resource_name="medication-service",
        summary="Deployment has unavailable replicas",
        event_time="2026-04-16T12:00:00Z",
        cluster="test-cluster",
        namespace="dev",
    )
    defaults.update(overrides)
    return NormalizedAlertEvent(**defaults)


def make_response(**overrides) -> CanonicalResponse:
    defaults = dict(
        request_id="req-123",
        result_state=ResultState.SUCCESS,
        summary="deployment medication-service is healthy: 2/2 ready, 2 available",
        actions_attempted=["get_deployment_status"],
        redaction_applied=True,
    )
    defaults.update(overrides)
    return CanonicalResponse(**defaults)


def test_format_investigation_reply_for_success() -> None:
    text = format_investigation_reply(
        make_event(),
        make_response(
            metadata={
                "health_state": "healthy",
                "attention_required": False,
                "resource_exists": True,
                "primary_reason": "Completed",
            },
        ),
    )

    assert "*Investigation Result*" in text
    assert "*Alert:* DeploymentReplicasMismatch" in text
    assert "*Target:* deployment/medication-service" in text
    assert "*Environment:* dev" in text
    assert "*Check:* get_deployment_status" in text
    assert "*Result:* success" in text
    assert "*State:* healthy" in text
    assert "*Reason:* Completed" in text
    assert "*Health:*" not in text
    assert "*Attention:*" not in text
    assert "*Exists:*" not in text
    assert "*Summary:* deployment medication-service is healthy: 2/2 ready, 2 available" in text


def test_format_investigation_reply_for_failed_result() -> None:
    text = format_investigation_reply(
        make_event(),
        make_response(
            result_state=ResultState.FAILED,
            summary="no registered tool available for get_deployment_status",
            actions_attempted=[],
        ),
    )

    assert "*Result:* failed" in text
    assert "*Check:* none" in text
    assert "*Summary:* no registered tool available for get_deployment_status" in text


def test_format_investigation_reply_omits_metadata_lines_when_unavailable() -> None:
    text = format_investigation_reply(make_event(), make_response())

    assert "*Health:*" not in text
    assert "*Attention:*" not in text
    assert "*Exists:*" not in text
    assert "*Reason:*" not in text


def test_format_investigation_reply_compacts_deleted_resource_metadata() -> None:
    text = format_investigation_reply(
        make_event(resource_type="pod", resource_name="worker-pod"),
        make_response(
            summary="pod worker-pod no longer exists; latest event=Normal/Scheduled",
            actions_attempted=["get_pod_events"],
            metadata={
                "health_state": "gone",
                "attention_required": False,
                "resource_exists": False,
                "primary_reason": "Deleted",
            },
        ),
    )

    assert "*State:* gone" in text
    assert "*Reason:* Deleted" in text
    assert "*Health:*" not in text
    assert "*Attention:*" not in text
    assert "*Exists:*" not in text


def test_format_investigation_reply_keeps_full_metadata_for_actionable_state() -> None:
    text = format_investigation_reply(
        make_event(resource_type="job", resource_name="nightly-backfill-12345"),
        make_response(
            summary="job nightly-backfill-12345 failed: active=0, succeeded=0, failed=3",
            actions_attempted=["get_job_status"],
            metadata={
                "health_state": "failed",
                "attention_required": True,
                "resource_exists": True,
                "primary_reason": "BackoffLimitExceeded",
            },
        ),
    )

    assert "*Health:* failed" in text
    assert "*Attention:* yes" in text
    assert "*Exists:* yes" in text
    assert "*Reason:* BackoffLimitExceeded" in text
    assert "*State:*" not in text
