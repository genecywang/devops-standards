from alert_auto_investigator.ingress.slack_message_parser import (
    parse_alertmanager_slack_message,
    parse_cloudwatch_slack_message,
)


def test_parse_alertmanager_message_returns_normalized_event() -> None:
    text = """AlertSource: prometheus
Environment: prod-jp
Cluster: H2-EKS-DEV-STG
Severity: critical
Status: firing
AlertName: HttpBlackboxProbeFailed
ResourceType: pod
ResourceName: backend-api-7f6d9
Namespace: backend
Summary: Backend API probe failed
Description: Http Probe down

RawLabels:
- alertname=HttpBlackboxProbeFailed
- cluster=H2-EKS-DEV-STG
"""

    event = parse_alertmanager_slack_message(
        text=text,
        region_code="ap-northeast-1",
        fallback_environment="staging-jp",
    )

    assert event is not None
    assert event.schema_version == "v1"
    assert event.source == "alertmanager"
    assert event.status == "firing"
    assert event.environment == "prod-jp"
    assert event.region_code == "ap-northeast-1"
    assert event.cluster == "H2-EKS-DEV-STG"
    assert event.namespace == "backend"
    assert event.alert_name == "HttpBlackboxProbeFailed"
    assert event.resource_type == "pod"
    assert event.resource_name == "backend-api-7f6d9"
    assert event.alert_key == "alertmanager:H2-EKS-DEV-STG:backend:HttpBlackboxProbeFailed:backend-api-7f6d9"
    assert event.raw_text == text


def test_parse_alertmanager_message_keeps_resolved_status() -> None:
    text = """AlertSource: prometheus
Environment: prod-jp
Cluster: H2-EKS-DEV-STG
Severity: warning
Status: resolved
AlertName: DeploymentReplicasMismatch
ResourceType: deployment
ResourceName: api
Namespace: backend
Summary: Deployment recovered
Description: -

RawLabels:
- alertname=DeploymentReplicasMismatch
"""

    event = parse_alertmanager_slack_message(
        text=text,
        region_code="ap-northeast-1",
        fallback_environment="staging-jp",
    )

    assert event is not None
    assert event.status == "resolved"


def test_parse_alertmanager_message_maps_unknown_status_to_unknown() -> None:
    text = """AlertSource: prometheus
Environment: prod-jp
Cluster: H2-EKS-DEV-STG
Severity: warning
Status: pending
AlertName: DeploymentReplicasMismatch
ResourceType: deployment
ResourceName: api
Namespace: backend
Summary: Deployment pending
Description: -

RawLabels:
- alertname=DeploymentReplicasMismatch
"""

    event = parse_alertmanager_slack_message(
        text=text,
        region_code="ap-northeast-1",
        fallback_environment="staging-jp",
    )

    assert event is not None
    assert event.status == "unknown"


def test_parse_alertmanager_message_returns_none_when_alert_name_missing() -> None:
    text = """AlertSource: prometheus
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
            region_code="ap-northeast-1",
            fallback_environment="staging-jp",
        )
        is None
    )


def test_parse_alertmanager_message_falls_back_when_environment_unknown() -> None:
    text = """AlertSource: prometheus
Environment: unknown
Cluster: H2-EKS-DEV-STG
Severity: critical
Status: firing
AlertName: HttpBlackboxProbeFailed
ResourceType: pod
ResourceName: backend-api-7f6d9
Namespace: backend
Summary: Backend API probe failed
Description: Http Probe down

RawLabels:
- alertname=HttpBlackboxProbeFailed
"""

    event = parse_alertmanager_slack_message(
        text=text,
        region_code="ap-northeast-1",
        fallback_environment="staging-jp",
    )

    assert event is not None
    assert event.environment == "staging-jp"


def test_parse_alertmanager_message_host_alert_key_excludes_namespace() -> None:
    text = """AlertSource: prometheus
Environment: prod-jp
Cluster: H2-EKS-DEV-STG
Severity: critical
Status: firing
AlertName: HostHighCpu
ResourceType: host
ResourceName: ip-10-0-0-12
Namespace: -
Summary: Host CPU high
Description: -

RawLabels:
- alertname=HostHighCpu
"""

    event = parse_alertmanager_slack_message(
        text=text,
        region_code="ap-northeast-1",
        fallback_environment="staging-jp",
    )

    assert event is not None
    assert event.alert_key == "alertmanager:H2-EKS-DEV-STG:HostHighCpu:ip-10-0-0-12"


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
