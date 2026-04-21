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


def make_analysis(**overrides) -> dict[str, object]:
    defaults = dict(
        summary="no infrastructure-side degradation is visible",
        current_interpretation="the service appears healthy from current signals",
        recommended_next_step="check CloudWatch metric trend before escalating",
        confidence="medium",
        caveats=["current-state only"],
    )
    defaults.update(overrides)
    return defaults


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


def test_format_investigation_reply_for_elasticache_success_uses_generic_contract() -> None:
    text = format_investigation_reply(
        make_event(
            source="cloudwatch_alarm",
            environment="prod-jp",
            region_code="ap-northeast-1",
            alert_name="ElastiCacheFreeableMemoryLow",
            alert_key="cloudwatch_alarm:416885395773:ap-northeast-1:ElastiCacheFreeableMemoryLow",
            resource_type="elasticache_cluster",
            resource_name="redis-prod",
            summary="CloudWatch alarm ALARM: ElastiCacheFreeableMemoryLow",
            cluster="",
            namespace="",
        ),
        make_response(
            summary=(
                "elasticache cluster redis-prod is available: engine=redis, engine_version=7.1, "
                "nodes=2, node_statuses=available=2, replication_group_id=present"
            ),
            actions_attempted=["get_elasticache_cluster_status"],
            metadata={
                "health_state": "healthy",
                "attention_required": False,
                "resource_exists": True,
                "primary_reason": "available",
            },
        ),
    )

    assert "*Alert:* ElastiCacheFreeableMemoryLow" in text
    assert "*Target:* elasticache_cluster/redis-prod" in text
    assert "*Environment:* prod-jp" in text
    assert "*Check:* get_elasticache_cluster_status" in text
    assert "*Result:* success" in text
    assert "*State:* healthy" in text
    assert "*Reason:* available" in text
    assert "*Summary:* elasticache cluster redis-prod is available:" in text
    assert "*Health:*" not in text
    assert "*Attention:*" not in text
    assert "*Exists:*" not in text


def test_format_investigation_reply_appends_related_k8s_lines_for_high_confidence_target_group() -> None:
    text = format_investigation_reply(
        make_event(
            alert_name="UnHealthyHostCount",
            resource_type="target_group",
            resource_name="targetgroup/k8s-dev-api/abc123",
            namespace="-",
        ),
        make_response(
            summary="target group targetgroup/k8s-dev-api/abc123 is unhealthy: healthy=0, unhealthy=2",
            actions_attempted=["get_target_group_status"],
            metadata={
                "health_state": "failed",
                "attention_required": True,
                "resource_exists": True,
                "primary_reason": "UnhealthyTargets",
            },
            enrichment={
                "confidence": "high",
                "namespace": "dev",
                "service_name": "h2-api",
            },
        ),
    )

    assert "RelatedK8sNamespace: dev" in text
    assert "RelatedK8sService: h2-api" in text


def test_format_investigation_reply_omits_related_k8s_lines_without_high_confidence() -> None:
    text = format_investigation_reply(
        make_event(resource_type="target_group", resource_name="targetgroup/k8s-dev-api/abc123"),
        make_response(
            actions_attempted=["get_target_group_status"],
            enrichment={"confidence": "not_applicable", "reason": "unsupported_target_type"},
        ),
    )

    assert "RelatedK8sNamespace:" not in text
    assert "RelatedK8sService:" not in text


def test_format_investigation_reply_appends_ai_analysis_section_when_provided() -> None:
    text = format_investigation_reply(
        make_event(),
        make_response(),
        analysis=make_analysis(),
    )

    assert "*AI Analysis*" in text
    assert "AI-generated" in text
    assert "verify before acting" in text
    assert "*Confidence:* medium" in text
    assert "*AI Summary:* no infrastructure-side degradation is visible" in text
    assert "*Interpretation:* the service appears healthy from current signals" in text
    assert "*Next Step:* check CloudWatch metric trend before escalating" in text
    assert "*Caveats:* current-state only" in text


def test_format_investigation_reply_omits_ai_analysis_section_when_incomplete() -> None:
    text = format_investigation_reply(
        make_event(),
        make_response(),
        analysis={"summary": "missing required fields"},
    )

    assert "*AI Analysis*" not in text
