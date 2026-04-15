from alert_auto_investigator.normalizers import alertmanager


def make_alert(
    status: str = "firing",
    alertname: str = "PodCrashLoopBackOff",
    cluster: str = "staging-main",
    namespace: str = "dev",
    pod: str | None = "dev-api-123",
    node: str | None = None,
    deployment: str | None = None,
    instance: str | None = None,
    severity: str = "critical",
    summary: str = "Pod is crash looping",
    description: str = "Pod has been restarting",
    starts_at: str = "2026-04-12T13:00:00Z",
    ends_at: str = "0001-01-01T00:00:00Z",
) -> dict:
    labels: dict = {
        "alertname": alertname,
        "cluster": cluster,
        "namespace": namespace,
        "severity": severity,
    }
    if pod is not None:
        labels["pod"] = pod
    if node is not None:
        labels["node"] = node
    if deployment is not None:
        labels["deployment"] = deployment
    if instance is not None:
        labels["instance"] = instance

    return {
        "status": status,
        "labels": labels,
        "annotations": {"summary": summary, "description": description},
        "startsAt": starts_at,
        "endsAt": ends_at,
    }


def test_normalize_pod_alert_returns_correct_fields() -> None:
    event = alertmanager.normalize(
        make_alert(),
        environment="prod-jp",
        region_code="ap-northeast-1",
    )

    assert event.schema_version == "v1"
    assert event.source == "alertmanager"
    assert event.status == "firing"
    assert event.environment == "prod-jp"
    assert event.region_code == "ap-northeast-1"
    assert event.alert_name == "PodCrashLoopBackOff"
    assert event.resource_type == "pod"
    assert event.resource_name == "dev-api-123"
    assert event.cluster == "staging-main"
    assert event.namespace == "dev"
    assert event.severity == "critical"
    assert event.summary == "Pod is crash looping"
    assert event.description == "Pod has been restarting"
    assert event.event_time == "2026-04-12T13:00:00Z"


def test_normalize_pod_alert_key_includes_namespace() -> None:
    event = alertmanager.normalize(
        make_alert(),
        environment="prod-jp",
        region_code="ap-northeast-1",
    )

    assert event.alert_key == "alertmanager:staging-main:dev:PodCrashLoopBackOff:dev-api-123"


def test_normalize_node_alert_resource_type() -> None:
    event = alertmanager.normalize(
        make_alert(pod=None, node="ip-10-0-1-5.ec2.internal"),
        environment="prod-jp",
        region_code="ap-northeast-1",
    )

    assert event.resource_type == "node"
    assert event.resource_name == "ip-10-0-1-5.ec2.internal"


def test_normalize_node_alert_key_excludes_namespace() -> None:
    event = alertmanager.normalize(
        make_alert(pod=None, node="ip-10-0-1-5.ec2.internal", alertname="HostOutOfMemory"),
        environment="prod-jp",
        region_code="ap-northeast-1",
    )

    assert event.alert_key == "alertmanager:staging-main:HostOutOfMemory:ip-10-0-1-5.ec2.internal"


def test_normalize_deployment_alert_resource_type() -> None:
    event = alertmanager.normalize(
        make_alert(pod=None, deployment="dev-api", alertname="DeploymentReplicasMismatch"),
        environment="prod-jp",
        region_code="ap-northeast-1",
    )

    assert event.resource_type == "deployment"
    assert event.resource_name == "dev-api"


def test_normalize_pod_takes_priority_over_deployment() -> None:
    event = alertmanager.normalize(
        make_alert(pod="dev-api-abc-123", deployment="dev-api"),
        environment="prod-jp",
        region_code="ap-northeast-1",
    )

    assert event.resource_type == "pod"
    assert event.resource_name == "dev-api-abc-123"


def test_normalize_instance_label_maps_to_node() -> None:
    event = alertmanager.normalize(
        make_alert(pod=None, instance="10.0.1.5:9100"),
        environment="prod-jp",
        region_code="ap-northeast-1",
    )

    assert event.resource_type == "node"
    assert event.resource_name == "10.0.1.5:9100"


def test_normalize_no_resource_labels_returns_unknown() -> None:
    event = alertmanager.normalize(
        make_alert(pod=None),
        environment="prod-jp",
        region_code="ap-northeast-1",
    )

    assert event.resource_type == "unknown"
    assert event.resource_name == "unknown"


def test_normalize_firing_uses_starts_at() -> None:
    event = alertmanager.normalize(
        make_alert(status="firing", starts_at="2026-04-12T13:00:00Z"),
        environment="prod-jp",
        region_code="ap-northeast-1",
    )

    assert event.event_time == "2026-04-12T13:00:00Z"


def test_normalize_resolved_uses_ends_at() -> None:
    event = alertmanager.normalize(
        make_alert(status="resolved", ends_at="2026-04-12T14:00:00Z"),
        environment="prod-jp",
        region_code="ap-northeast-1",
    )

    assert event.status == "resolved"
    assert event.event_time == "2026-04-12T14:00:00Z"


def test_normalize_unknown_status() -> None:
    event = alertmanager.normalize(
        make_alert(status="pending"),
        environment="prod-jp",
        region_code="ap-northeast-1",
    )

    assert event.status == "unknown"


def test_normalize_missing_summary_falls_back_to_alert_name() -> None:
    alert = make_alert()
    del alert["annotations"]["summary"]
    event = alertmanager.normalize(alert, environment="prod-jp", region_code="ap-northeast-1")

    assert event.summary == "Alertmanager alert: PodCrashLoopBackOff"


def test_normalize_preserves_raw_payload() -> None:
    alert = make_alert()
    event = alertmanager.normalize(alert, environment="prod-jp", region_code="ap-northeast-1")

    assert event.raw_payload is alert
