from __future__ import annotations

import json
from pathlib import Path

from openclaw_foundation.models.enums import ResultState
from openclaw_foundation.models.responses import CanonicalResponse

from alert_auto_investigator.ingress.slack_message_parser import (
    parse_alertmanager_slack_message,
    parse_alertmanager_slack_messages,
)
from alert_auto_investigator.investigation.dispatcher import (
    DEFAULT_TOOL_ROUTING,
    InvestigationConfig,
    OpenClawDispatcher,
)
from alert_auto_investigator.models.normalized_alert_event import NormalizedAlertEvent
from alert_auto_investigator.normalizers import cloudwatch_alarm
from alert_auto_investigator.service.formatter import format_investigation_reply

_FIXTURE_DIR = Path(__file__).parent / "fixtures"
_REGION = "ap-northeast-1"
_FALLBACK_ENV = "staging-jp"


def _load_fixture(name: str) -> str:
    return (_FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_json_fixture(name: str) -> dict[str, object]:
    return json.loads(_load_fixture(name))


def _parse_fixture(name: str) -> NormalizedAlertEvent:
    event = parse_alertmanager_slack_message(
        text=_load_fixture(name),
        region_code=_REGION,
        fallback_environment=_FALLBACK_ENV,
    )
    assert event is not None
    return event


def _parse_multi_fixture(name: str) -> list[NormalizedAlertEvent]:
    return parse_alertmanager_slack_messages(
        text=_load_fixture(name),
        region_code=_REGION,
        fallback_environment=_FALLBACK_ENV,
    )


def _make_response(summary: str, metadata: dict[str, object], check: str) -> CanonicalResponse:
    return CanonicalResponse(
        request_id="req-golden-001",
        result_state=ResultState.SUCCESS,
        summary=summary,
        actions_attempted=[check],
        redaction_applied=True,
        metadata=metadata,
    )


class _RunnerStub:
    def __init__(self) -> None:
        self.last_request = None

    def run(self, request):
        self.last_request = request
        return object()


def test_golden_parser_job_failed_replay() -> None:
    event = _parse_fixture("alertmanager_job_failed.txt")

    assert event.alert_name == "KubernetesJobFailed"
    assert event.resource_type == "job"
    assert event.resource_name == "cronjob-iam-user-keyscan-manual-86x"
    assert event.namespace == "monitoring"
    assert (
        event.alert_key
        == "alertmanager:H2S-EKS-DEV-STG-EAST-2:monitoring:KubernetesJobFailed:cronjob-iam-user-keyscan-manual-86x"
    )


def test_golden_parser_job_slow_completion_replay() -> None:
    event = _parse_fixture("alertmanager_job_slow_completion.txt")

    assert event.alert_name == "KubernetesJobSlowCompletion"
    assert event.resource_type == "job"
    assert event.resource_name == "cronjob-iam-user-keyscan-manual-86x"
    assert event.namespace == "monitoring"
    assert (
        event.alert_key
        == "alertmanager:H2S-EKS-DEV-STG-EAST-2:monitoring:KubernetesJobSlowCompletion:cronjob-iam-user-keyscan-manual-86x"
    )


def test_golden_parser_deployment_replay() -> None:
    event = _parse_fixture("alertmanager_deployment_healthy.txt")

    assert event.alert_name == "DeploymentReplicasMismatch"
    assert event.resource_type == "deployment"
    assert event.resource_name == "medication-service"
    assert event.namespace == "dev"
    assert (
        event.alert_key
        == "alertmanager:H2S-EKS-DEV-STG-EAST-2:dev:DeploymentReplicasMismatch:medication-service"
    )


def test_golden_parser_cronjob_replay() -> None:
    event = _parse_fixture("alertmanager_cronjob_parser.txt")

    assert event.alert_name == "KubernetesCronjobSuspended"
    assert event.resource_type == "cronjob"
    assert event.resource_name == "nightly-backfill"
    assert event.namespace == "dev"
    assert (
        event.alert_key
        == "alertmanager:H2S-EKS-DEV-STG-EAST-2:dev:KubernetesCronjobSuspended:nightly-backfill"
    )


def test_golden_parser_cronjob_idle_replay() -> None:
    event = _parse_fixture("alertmanager_cronjob_idle.txt")

    assert event.alert_name == "KubernetesCronjobIdle"
    assert event.resource_type == "cronjob"
    assert event.resource_name == "nightly-backfill"
    assert event.namespace == "dev"
    assert (
        event.alert_key
        == "alertmanager:H2S-EKS-DEV-STG-EAST-2:dev:KubernetesCronjobIdle:nightly-backfill"
    )


def test_golden_parser_multi_alert_replay_returns_all_alerts() -> None:
    events = _parse_multi_fixture("alertmanager_multi_pod_oom.txt")

    assert len(events) == 2
    assert events[0].resource_type == "pod"
    assert events[1].resource_type == "pod"
    assert events[0].resource_name == "prod-h2-lab-worker-6dfcbbbff4-55w6b"
    assert events[1].resource_name == "prod-h2-server-go-567589445c-n8b9s"
    assert events[0].alert_key != events[1].alert_key


def test_golden_parser_pod_healthy_replay() -> None:
    event = _parse_fixture("alertmanager_pod_healthy.txt")

    assert event.alert_name == "KubernetesPod not in running status"
    assert event.resource_type == "pod"
    assert event.resource_name == "dev-py3-h2s-apisvc-7b866db5cd-qfg95"
    assert event.namespace == "dev"
    assert (
        event.alert_key
        == "alertmanager:H2S-EKS-DEV-STG-EAST-2:dev:KubernetesPod not in running status:dev-py3-h2s-apisvc-7b866db5cd-qfg95"
    )


def test_golden_parser_pod_gone_replay() -> None:
    event = _parse_fixture("alertmanager_pod_gone.txt")

    assert event.alert_name == "KubernetesPod not in running status"
    assert event.resource_type == "pod"
    assert event.resource_name == "worker-pod-gone"
    assert event.namespace == "dev"
    assert (
        event.alert_key
        == "alertmanager:H2S-EKS-DEV-STG-EAST-2:dev:KubernetesPod not in running status:worker-pod-gone"
    )


def test_golden_parser_pod_oomkilled_replay() -> None:
    event = _parse_fixture("alertmanager_pod_oomkilled.txt")

    assert event.alert_name == "KubernetesContainerOomKiller"
    assert event.resource_type == "pod"
    assert event.resource_name == "prod-h2-server-go-567589445c-n8b9s"
    assert event.namespace == "prod"
    assert (
        event.alert_key
        == "alertmanager:H2S-EKS-DEV-STG-EAST-2:prod:KubernetesContainerOomKiller:prod-h2-server-go-567589445c-n8b9s"
    )


def test_golden_cloudwatch_elasticache_alarm_replay_normalizes_and_routes() -> None:
    payload = _load_json_fixture("cloudwatch_elasticache_alarm.json")
    event = cloudwatch_alarm.normalize(payload, environment="prod-jp")
    runner = _RunnerStub()
    dispatcher = OpenClawDispatcher(
        runner=runner,
        config=InvestigationConfig(tool_routing=dict(DEFAULT_TOOL_ROUTING)),
    )

    assert payload["Trigger"]["Dimensions"] == [
        {"name": "CacheNodeId", "value": "redis-prod-001"},
        {"name": "CacheClusterId", "value": "redis-prod"},
    ]
    assert event.resource_type == "elasticache_cluster"
    assert event.resource_name == "redis-prod"
    assert event.account_id == "416885395773"
    assert event.region_code == "ap-northeast-1"

    response = dispatcher.dispatch(event)

    assert response is not None
    assert runner.last_request.tool_name == "get_elasticache_cluster_status"


def test_golden_skip_by_design_namespace_replay(caplog) -> None:
    event = _parse_fixture("alertmanager_namespace_skip.txt")
    dispatcher = OpenClawDispatcher(
        runner=_RunnerStub(),
        config=InvestigationConfig(tool_routing=dict(DEFAULT_TOOL_ROUTING)),
    )

    with caplog.at_level("DEBUG"):
        result = dispatcher.dispatch(event)

    assert result is None
    assert "dispatch_skipped_no_tool resource_type=namespace policy=skip_by_design" in caplog.text


def test_golden_formatter_compacts_healthy_pod_reply() -> None:
    event = _parse_fixture("alertmanager_pod_healthy.txt")
    response = _make_response(
        summary="pod dev-py3-h2s-apisvc-7b866db5cd-qfg95 is Running; no recent Warning events",
        check="get_pod_events",
        metadata={
            "health_state": "healthy",
            "attention_required": False,
            "resource_exists": True,
            "primary_reason": "Running",
        },
    )

    text = format_investigation_reply(event, response)

    assert "*State:* healthy" in text
    assert "*Reason:* Running" in text
    assert "*Health:*" not in text
    assert "*Attention:*" not in text
    assert "*Exists:*" not in text


def test_golden_formatter_keeps_full_metadata_for_failed_job_reply() -> None:
    event = _parse_fixture("alertmanager_job_failed.txt")
    response = _make_response(
        summary=(
            "job cronjob-iam-user-keyscan-manual-86x failed: active=0, succeeded=0, failed=3, "
            "reason=BackoffLimitExceeded, message=Job has reached the specified backoff limit"
        ),
        check="get_job_status",
        metadata={
            "health_state": "failed",
            "attention_required": True,
            "resource_exists": True,
            "primary_reason": "BackoffLimitExceeded",
        },
    )

    text = format_investigation_reply(event, response)

    assert "*Health:* failed" in text
    assert "*Attention:* yes" in text
    assert "*Exists:* yes" in text
    assert "*Reason:* BackoffLimitExceeded" in text


def test_golden_formatter_keeps_full_metadata_for_job_slow_completion_reply() -> None:
    event = _parse_fixture("alertmanager_job_slow_completion.txt")
    response = _make_response(
        summary=(
            "job cronjob-iam-user-keyscan-manual-86x failed: active=0, succeeded=0, failed=3, "
            "reason=BackoffLimitExceeded, message=Job has reached the specified backoff limit"
        ),
        check="get_job_status",
        metadata={
            "health_state": "failed",
            "attention_required": True,
            "resource_exists": True,
            "primary_reason": "BackoffLimitExceeded",
        },
    )

    text = format_investigation_reply(event, response)

    assert "*Alert:* KubernetesJobSlowCompletion" in text
    assert "*Health:* failed" in text
    assert "*Attention:* yes" in text
    assert "*Exists:* yes" in text
    assert "*Reason:* BackoffLimitExceeded" in text


def test_golden_formatter_compacts_healthy_deployment_reply() -> None:
    event = _parse_fixture("alertmanager_deployment_healthy.txt")
    response = _make_response(
        summary="deployment medication-service is healthy: 3/3 ready, 3 available",
        check="get_deployment_status",
        metadata={
            "health_state": "healthy",
            "attention_required": False,
            "resource_exists": True,
            "primary_reason": "MinimumReplicasAvailable",
        },
    )

    text = format_investigation_reply(event, response)

    assert "*State:* healthy" in text
    assert "*Reason:* MinimumReplicasAvailable" in text
    assert "*Health:*" not in text
    assert "*Attention:*" not in text
    assert "*Exists:*" not in text


def test_golden_formatter_compacts_gone_pod_reply() -> None:
    event = _parse_fixture("alertmanager_pod_gone.txt")
    response = _make_response(
        summary="pod worker-pod-gone no longer exists; latest event=Normal/Scheduled",
        check="get_pod_events",
        metadata={
            "health_state": "gone",
            "attention_required": False,
            "resource_exists": False,
            "primary_reason": "Deleted",
        },
    )

    text = format_investigation_reply(event, response)

    assert "*State:* gone" in text
    assert "*Reason:* Deleted" in text
    assert "*Health:*" not in text
    assert "*Attention:*" not in text
    assert "*Exists:*" not in text


def test_golden_formatter_keeps_full_metadata_for_degraded_pod_reply() -> None:
    event = _parse_fixture("alertmanager_pod_oomkilled.txt")
    response = _make_response(
        summary=(
            "pod prod-h2-server-go-567589445c-n8b9s is Running but needs attention; "
            "container app last terminated reason=OOMKilled exit_code=137 restart_count=4; no recent events"
        ),
        check="get_pod_events",
        metadata={
            "health_state": "degraded",
            "attention_required": True,
            "resource_exists": True,
            "primary_reason": "OOMKilled",
        },
    )

    text = format_investigation_reply(event, response)

    assert "*Health:* degraded" in text
    assert "*Attention:* yes" in text
    assert "*Exists:* yes" in text
    assert "*Reason:* OOMKilled" in text
    assert "*State:*" not in text


def test_golden_formatter_compacts_suspended_cronjob_reply() -> None:
    event = _parse_fixture("alertmanager_cronjob_suspended.txt")
    response = _make_response(
        summary='cronjob nightly-backfill schedule="*/30 * * * *" suspend=true last_schedule=2026-04-18T02:30:00Z is suspended; no recent jobs',
        check="get_cronjob_status",
        metadata={
            "health_state": "suspended",
            "attention_required": False,
            "resource_exists": True,
            "primary_reason": "Suspended",
        },
    )

    text = format_investigation_reply(event, response)

    assert "*Health:* suspended" in text
    assert "*Attention:* no" in text
    assert "*Exists:* yes" in text
    assert "*Reason:* Suspended" in text


def test_golden_formatter_keeps_full_metadata_for_idle_cronjob_reply() -> None:
    event = _parse_fixture("alertmanager_cronjob_idle.txt")
    response = _make_response(
        summary='cronjob nightly-backfill schedule="*/30 * * * *" suspend=false last_schedule=2026-04-18T02:30:00Z has no recent jobs',
        check="get_cronjob_status",
        metadata={
            "health_state": "idle",
            "attention_required": False,
            "resource_exists": True,
            "primary_reason": "NoRecentJobs",
        },
    )

    text = format_investigation_reply(event, response)

    assert "*Health:* idle" in text
    assert "*Attention:* no" in text
    assert "*Exists:* yes" in text
    assert "*Reason:* NoRecentJobs" in text
