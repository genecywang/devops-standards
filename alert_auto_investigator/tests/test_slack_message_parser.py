from alert_auto_investigator.ingress.slack_message_parser import (
    parse_alertmanager_slack_message,
    parse_alertmanager_slack_messages,
    parse_cloudwatch_slack_message,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REGION = "ap-northeast-1"
_FALLBACK_ENV = "staging-jp"


def _alertmanager_text(
    alert_name: str = "HttpBlackboxProbeFailed",
    resource_type: str = "pod",
    resource_name: str = "backend-api-7f6d9",
    namespace: str = "backend",
    environment: str = "prod-jp",
    status: str = "firing",
    severity: str = "critical",
    summary: str = "Backend API probe failed",
    description: str = "Http Probe down",
) -> str:
    return f"""\
Alert: {alert_name}
Resource: {resource_name}
Environment: {environment}

--- Structured Alert ---
AlertSource: prometheus
Environment: {environment}
Cluster: H2-EKS-DEV-STG
Severity: {severity}
Status: {status}
AlertName: {alert_name}
ResourceType: {resource_type}
ResourceName: {resource_name}
Namespace: {namespace}
Summary: {summary}
Description: {description}

RawLabels:
- alertname={alert_name}
- cluster=H2-EKS-DEV-STG
"""


# ---------------------------------------------------------------------------
# parse_alertmanager_slack_message — single alert
# ---------------------------------------------------------------------------


def test_parse_alertmanager_message_returns_normalized_event() -> None:
    event = parse_alertmanager_slack_message(
        text=_alertmanager_text(),
        region_code=_REGION,
        fallback_environment=_FALLBACK_ENV,
    )

    assert event is not None
    assert event.schema_version == "v1"
    assert event.source == "alertmanager"
    assert event.status == "firing"
    assert event.environment == "prod-jp"
    assert event.region_code == _REGION
    assert event.cluster == "H2-EKS-DEV-STG"
    assert event.namespace == "backend"
    assert event.alert_name == "HttpBlackboxProbeFailed"
    assert event.resource_type == "pod"
    assert event.resource_name == "backend-api-7f6d9"
    assert event.alert_key == "alertmanager:H2-EKS-DEV-STG:backend:HttpBlackboxProbeFailed:backend-api-7f6d9"


def test_parse_alertmanager_message_keeps_resolved_status() -> None:
    event = parse_alertmanager_slack_message(
        text=_alertmanager_text(alert_name="DeploymentReplicasMismatch", resource_type="deployment", resource_name="api", status="resolved"),
        region_code=_REGION,
        fallback_environment=_FALLBACK_ENV,
    )

    assert event is not None
    assert event.status == "resolved"


def test_parse_alertmanager_message_maps_unknown_status_to_unknown() -> None:
    event = parse_alertmanager_slack_message(
        text=_alertmanager_text(alert_name="DeploymentReplicasMismatch", resource_type="deployment", resource_name="api", status="pending"),
        region_code=_REGION,
        fallback_environment=_FALLBACK_ENV,
    )

    assert event is not None
    assert event.status == "unknown"


def test_parse_alertmanager_message_returns_none_when_alert_name_missing() -> None:
    text = """\
--- Structured Alert ---
AlertSource: prometheus
Environment: prod-jp
Cluster: H2-EKS-DEV-STG
Severity: critical
Status: firing
ResourceType: pod
ResourceName: backend-api-7f6d9
Namespace: backend
Summary: Backend API probe failed
Description: Http Probe down

RawLabels:
- cluster=H2-EKS-DEV-STG
"""
    assert (
        parse_alertmanager_slack_message(
            text=text,
            region_code=_REGION,
            fallback_environment=_FALLBACK_ENV,
        )
        is None
    )


def test_parse_alertmanager_message_falls_back_when_environment_unknown() -> None:
    event = parse_alertmanager_slack_message(
        text=_alertmanager_text(environment="unknown"),
        region_code=_REGION,
        fallback_environment=_FALLBACK_ENV,
    )

    assert event is not None
    assert event.environment == _FALLBACK_ENV


def test_parse_alertmanager_message_host_alert_key_excludes_namespace() -> None:
    event = parse_alertmanager_slack_message(
        text=_alertmanager_text(
            alert_name="NodeHighCpu",
            resource_type="node",
            resource_name="ip-10-0-0-12",
            namespace="-",
            summary="Node CPU high",
            description="-",
        ),
        region_code=_REGION,
        fallback_environment=_FALLBACK_ENV,
    )

    assert event is not None
    assert event.alert_key == "alertmanager:H2-EKS-DEV-STG:NodeHighCpu:ip-10-0-0-12"


def test_instance_alert_slack_parser_and_webhook_normalizer_both_map_to_node() -> None:
    from alert_auto_investigator.normalizers.alertmanager import normalize

    slack_event = parse_alertmanager_slack_message(
        text=_alertmanager_text(
            alert_name="NodeOomKillDetected",
            resource_type="node",
            resource_name="ip-10-0-0-12.ap-northeast-1.compute.internal",
            namespace="-",
            summary="Node OOM kill detected",
            description="OOM kill detected",
        ),
        region_code=_REGION,
        fallback_environment=_FALLBACK_ENV,
    )
    webhook_event = normalize(
        {
            "status": "firing",
            "startsAt": "2026-04-17T08:00:00Z",
            "endsAt": "2026-04-17T08:05:00Z",
            "labels": {
                "alertname": "NodeOomKillDetected",
                "cluster": "H2-EKS-DEV-STG",
                "namespace": "backend",
                "severity": "critical",
                "instance": "ip-10-0-0-12.ap-northeast-1.compute.internal",
            },
            "annotations": {
                "summary": "Node OOM kill detected",
                "description": "OOM kill detected",
            },
        },
        environment="prod-jp",
        region_code=_REGION,
    )

    assert slack_event is not None
    assert slack_event.resource_type == "node"
    assert webhook_event.resource_type == "node"


def test_parse_alertmanager_message_job_name_maps_to_job() -> None:
    event = parse_alertmanager_slack_message(
        text=_alertmanager_text(
            alert_name="KubernetesJobSlowCompletion",
            resource_type="job",
            resource_name="nightly-backfill-12345",
            namespace="batch",
            summary="Kubernetes job slow completion",
            description="Kubernetes Job batch/nightly-backfill-12345 did not complete in time",
        ),
        region_code=_REGION,
        fallback_environment=_FALLBACK_ENV,
    )

    assert event is not None
    assert event.resource_type == "job"
    assert event.resource_name == "nightly-backfill-12345"
    assert event.alert_key == "alertmanager:H2-EKS-DEV-STG:KubernetesJobSlowCompletion:nightly-backfill-12345"


def test_parse_alertmanager_message_exported_job_maps_to_job() -> None:
    text = """\
Alert: KubernetesJobFailed
Resource: nightly-backfill-12345
Environment: prod-jp

--- Structured Alert ---
AlertSource: prometheus
Environment: prod-jp
Cluster: H2-EKS-DEV-STG
Severity: warning
Status: firing
AlertName: KubernetesJobFailed
ResourceType: job
ResourceName: nightly-backfill-12345
Namespace: batch
Summary: Kubernetes Job failed
Description: Job batch/nightly-backfill-12345 failed to complete

RawLabels:
- alertname=KubernetesJobFailed
- exported_job=nightly-backfill-12345
- namespace=batch
"""

    event = parse_alertmanager_slack_message(
        text=text,
        region_code=_REGION,
        fallback_environment=_FALLBACK_ENV,
    )

    assert event is not None
    assert event.resource_type == "job"
    assert event.resource_name == "nightly-backfill-12345"
    assert event.alert_key == "alertmanager:H2-EKS-DEV-STG:KubernetesJobFailed:nightly-backfill-12345"


def test_parse_alertmanager_message_cronjob_maps_to_cronjob() -> None:
    event = parse_alertmanager_slack_message(
        text=_alertmanager_text(
            alert_name="KubernetesCronjobTooLong",
            resource_type="cronjob",
            resource_name="nightly-backfill",
            namespace="batch",
            summary="Kubernetes CronJob too long",
            description="CronJob batch/nightly-backfill is taking more than 1h to complete",
        ),
        region_code=_REGION,
        fallback_environment=_FALLBACK_ENV,
    )

    assert event is not None
    assert event.resource_type == "cronjob"
    assert event.resource_name == "nightly-backfill"
    assert event.alert_key == "alertmanager:H2-EKS-DEV-STG:KubernetesCronjobTooLong:nightly-backfill"


def test_parse_alertmanager_message_does_not_infer_job_from_scrape_job_label() -> None:
    text = """\
Alert: KubernetesContainerOomKiller
Resource: prod
Environment: prod-jp

--- Structured Alert ---
AlertSource: prometheus
Environment: prod-jp
Cluster: H2-EKS-DEV-STG
Severity: critical
Status: firing
AlertName: KubernetesContainerOomKiller
ResourceType: namespace
ResourceName: prod
Namespace: prod
Summary: Kubernetes container oom killer
Description: Pod in namespace prod was OOMKilled

RawLabels:
- alertname=KubernetesContainerOomKiller
- job=kubernetes-service-endpoints
- namespace=prod
"""

    event = parse_alertmanager_slack_message(
        text=text,
        region_code=_REGION,
        fallback_environment=_FALLBACK_ENV,
    )

    assert event is not None
    assert event.resource_type == "namespace"
    assert event.resource_name == "prod"


def test_parse_alertmanager_message_returns_none_without_marker() -> None:
    text = "AlertSource: prometheus\nAlertName: Test\n"
    assert (
        parse_alertmanager_slack_message(
            text=text,
            region_code=_REGION,
            fallback_environment=_FALLBACK_ENV,
        )
        is None
    )


# ---------------------------------------------------------------------------
# parse_alertmanager_slack_messages — multi-alert
# ---------------------------------------------------------------------------


def test_parse_alertmanager_messages_returns_all_alerts() -> None:
    """[FIRING:2] message with two pod alerts produces two NormalizedAlertEvents."""
    text = """\
[FIRING:2] KubernetesContainerOomKiller | prod-jp | H2S-EKS-PROD-NORTHEAST-1
Alert: KubernetesContainerOomKiller
Resource: prod-h2-lab-worker-6dfcbbbff4-55w6b

--- Structured Alert ---
AlertSource: prometheus
Environment: prod-jp
Cluster: H2S-EKS-PROD-NORTHEAST-1
Severity: critical
Status: firing
AlertName: KubernetesContainerOomKiller
ResourceType: pod
ResourceName: prod-h2-lab-worker-6dfcbbbff4-55w6b
Namespace: prod
Summary: Container OOMKilled
Description: OOMKilled 1 time

RawLabels:
- alertname=KubernetesContainerOomKiller
- pod=prod-h2-lab-worker-6dfcbbbff4-55w6b

Alert: KubernetesContainerOomKiller
Resource: prod-h2-server-go-567589445c-n8b9s

--- Structured Alert ---
AlertSource: prometheus
Environment: prod-jp
Cluster: H2S-EKS-PROD-NORTHEAST-1
Severity: critical
Status: firing
AlertName: KubernetesContainerOomKiller
ResourceType: pod
ResourceName: prod-h2-server-go-567589445c-n8b9s
Namespace: prod
Summary: Container OOMKilled
Description: OOMKilled 1 time

RawLabels:
- alertname=KubernetesContainerOomKiller
- pod=prod-h2-server-go-567589445c-n8b9s
"""

    events = parse_alertmanager_slack_messages(text, region_code=_REGION, fallback_environment=_FALLBACK_ENV)

    assert len(events) == 2
    assert events[0].resource_name == "prod-h2-lab-worker-6dfcbbbff4-55w6b"
    assert events[1].resource_name == "prod-h2-server-go-567589445c-n8b9s"
    assert events[0].alert_name == "KubernetesContainerOomKiller"
    assert events[1].alert_name == "KubernetesContainerOomKiller"
    assert events[0].alert_key != events[1].alert_key


def test_parse_alertmanager_messages_returns_empty_without_marker() -> None:
    assert parse_alertmanager_slack_messages("no marker here", _REGION, _FALLBACK_ENV) == []


def test_parse_alertmanager_messages_skips_invalid_block() -> None:
    """A block missing required fields is silently skipped; valid blocks are still returned."""
    text = """\
--- Structured Alert ---
AlertSource: prometheus
Environment: prod-jp
Cluster: H2-EKS-DEV-STG
Severity: critical
Status: firing
AlertName: GoodAlert
ResourceType: pod
ResourceName: good-pod
Namespace: prod
Summary: Good alert

RawLabels:
- alertname=GoodAlert

--- Structured Alert ---
AlertSource: prometheus
Environment: prod-jp
Cluster: H2-EKS-DEV-STG
Status: firing

RawLabels:
- alertname=BadAlert
"""

    events = parse_alertmanager_slack_messages(text, region_code=_REGION, fallback_environment=_FALLBACK_ENV)

    assert len(events) == 1
    assert events[0].alert_name == "GoodAlert"


# ---------------------------------------------------------------------------
# parse_cloudwatch_slack_message
# ---------------------------------------------------------------------------


def test_parse_cloudwatch_message_returns_normalized_event() -> None:
    text = """[FIRING]
AWS Account : 416885395773
AlarmName : p-rds-shuriken_ReadIOPS

--- Structured Alert ---
schema_version: v1
source: cloudwatch_alarm
status: ALARM
alert_name: p-rds-shuriken_ReadIOPS
account_id: 416885395773
region_code: ap-northeast-1
environment: prod-jp
event_time: 2026-04-13T15:02:59.759+0000
alert_key: cloudwatch_alarm:416885395773:ap-northeast-1:p-rds-shuriken_ReadIOPS
resource_type: rds_instance
resource_name: shuriken
"""

    event = parse_cloudwatch_slack_message(text)

    assert event is not None
    assert event.schema_version == "v1"
    assert event.source == "cloudwatch_alarm"
    assert event.status == "firing"
    assert event.alert_name == "p-rds-shuriken_ReadIOPS"
    assert event.alert_key == "cloudwatch_alarm:416885395773:ap-northeast-1:p-rds-shuriken_ReadIOPS"
    assert event.resource_type == "rds_instance"
    assert event.resource_name == "shuriken"
    assert event.raw_text == text


def test_parse_cloudwatch_message_returns_none_without_marker() -> None:
    text = """[FIRING]
AWS Account : 416885395773
AlarmName : p-rds-shuriken_ReadIOPS
"""

    assert parse_cloudwatch_slack_message(text) is None


def test_parse_cloudwatch_message_maps_ok_to_resolved() -> None:
    text = """--- Structured Alert ---
schema_version: v1
source: cloudwatch_alarm
status: OK
alert_name: p-rds-shuriken_ReadIOPS
account_id: 416885395773
region_code: ap-northeast-1
environment: prod-jp
event_time: 2026-04-13T15:02:59.759+0000
alert_key: cloudwatch_alarm:416885395773:ap-northeast-1:p-rds-shuriken_ReadIOPS
resource_type: rds_instance
resource_name: shuriken
"""

    event = parse_cloudwatch_slack_message(text)

    assert event is not None
    assert event.status == "resolved"
