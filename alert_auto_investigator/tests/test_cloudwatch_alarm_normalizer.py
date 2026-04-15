from alert_auto_investigator.normalizers import cloudwatch_alarm


def make_payload(
    alarm_name: str = "p-rds-shuriken_ReadIOPS",
    state: str = "ALARM",
    account_id: str = "416885395773",
    region: str = "ap-northeast-1",
    dimensions: list[dict] | None = None,
    metric_name: str = "ReadIOPS",
    namespace: str = "AWS/RDS",
    reason: str = "Threshold Crossed",
    state_change_time: str = "2026-04-12T13:05:43.360+0000",
) -> dict:
    if dimensions is None:
        dimensions = [{"name": "DBInstanceIdentifier", "value": "shuriken"}]
    return {
        "AlarmName": alarm_name,
        "AlarmArn": f"arn:aws:cloudwatch:{region}:{account_id}:alarm:{alarm_name}",
        "AWSAccountId": account_id,
        "NewStateValue": state,
        "NewStateReason": reason,
        "StateChangeTime": state_change_time,
        "Trigger": {
            "MetricName": metric_name,
            "Namespace": namespace,
            "Dimensions": dimensions,
        },
    }


def test_normalize_rds_alarm_returns_correct_fields() -> None:
    event = cloudwatch_alarm.normalize(make_payload(), environment="prod-jp")

    assert event.schema_version == "v1"
    assert event.source == "cloudwatch_alarm"
    assert event.status == "firing"
    assert event.environment == "prod-jp"
    assert event.region_code == "ap-northeast-1"
    assert event.account_id == "416885395773"
    assert event.alert_name == "p-rds-shuriken_ReadIOPS"
    assert event.resource_type == "rds_instance"
    assert event.resource_name == "shuriken"
    assert event.namespace == "AWS/RDS"
    assert event.metric_name == "ReadIOPS"
    assert event.description == "Threshold Crossed"
    assert event.event_time == "2026-04-12T13:05:43.360+0000"


def test_normalize_builds_correct_alert_key() -> None:
    event = cloudwatch_alarm.normalize(make_payload(), environment="prod-jp")

    assert event.alert_key == "cloudwatch_alarm:416885395773:ap-northeast-1:p-rds-shuriken_ReadIOPS"


def test_normalize_maps_alarm_state_to_firing() -> None:
    event = cloudwatch_alarm.normalize(make_payload(state="ALARM"), environment="prod-jp")

    assert event.status == "firing"


def test_normalize_maps_ok_state_to_resolved() -> None:
    event = cloudwatch_alarm.normalize(make_payload(state="OK"), environment="prod-jp")

    assert event.status == "resolved"


def test_normalize_maps_unknown_state() -> None:
    event = cloudwatch_alarm.normalize(make_payload(state="INSUFFICIENT_DATA"), environment="prod-jp")

    assert event.status == "unknown"


def test_normalize_maps_ec2_dimension() -> None:
    payload = make_payload(dimensions=[{"name": "InstanceId", "value": "i-0abc123"}])
    event = cloudwatch_alarm.normalize(payload, environment="prod-jp")

    assert event.resource_type == "ec2_instance"
    assert event.resource_name == "i-0abc123"


def test_normalize_maps_eks_cluster_dimension() -> None:
    payload = make_payload(dimensions=[{"name": "ClusterName", "value": "prod-main"}])
    event = cloudwatch_alarm.normalize(payload, environment="prod-jp")

    assert event.resource_type == "eks_cluster"
    assert event.resource_name == "prod-main"


def test_normalize_maps_load_balancer_dimension() -> None:
    payload = make_payload(dimensions=[{"name": "LoadBalancer", "value": "app/my-lb/abc123"}])
    event = cloudwatch_alarm.normalize(payload, environment="prod-jp")

    assert event.resource_type == "load_balancer"
    assert event.resource_name == "app/my-lb/abc123"


def test_normalize_unknown_dimension_returns_unknown_resource() -> None:
    payload = make_payload(dimensions=[{"name": "QueueName", "value": "my-queue"}])
    event = cloudwatch_alarm.normalize(payload, environment="prod-jp")

    assert event.resource_type == "unknown"
    assert event.resource_name == "unknown"


def test_normalize_empty_dimensions_returns_unknown_resource() -> None:
    payload = make_payload(dimensions=[])
    event = cloudwatch_alarm.normalize(payload, environment="prod-jp")

    assert event.resource_type == "unknown"
    assert event.resource_name == "unknown"


def test_normalize_missing_alarm_arn_produces_empty_region_code() -> None:
    payload = make_payload()
    del payload["AlarmArn"]
    event = cloudwatch_alarm.normalize(payload, environment="prod-jp")

    assert event.region_code == ""


def test_normalize_preserves_raw_payload() -> None:
    payload = make_payload()
    event = cloudwatch_alarm.normalize(payload, environment="prod-jp")

    assert event.raw_payload is payload
