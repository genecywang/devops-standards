from alert_auto_investigator.models.normalized_alert_event import NormalizedAlertEvent


def make_event(**overrides) -> NormalizedAlertEvent:
    defaults = dict(
        schema_version="v1",
        source="cloudwatch_alarm",
        status="firing",
        environment="prod-jp",
        region_code="ap-northeast-1",
        alert_name="p-rds-shuriken_ReadIOPS",
        alert_key="cloudwatch_alarm:123456789:ap-northeast-1:p-rds-shuriken_ReadIOPS",
        resource_type="rds_instance",
        resource_name="shuriken",
        summary="CloudWatch alarm triggered",
        event_time="2026-04-12T13:05:43Z",
    )
    defaults.update(overrides)
    return NormalizedAlertEvent(**defaults)


def test_required_fields_are_set() -> None:
    event = make_event()

    assert event.schema_version == "v1"
    assert event.source == "cloudwatch_alarm"
    assert event.status == "firing"
    assert event.environment == "prod-jp"
    assert event.region_code == "ap-northeast-1"
    assert event.alert_name == "p-rds-shuriken_ReadIOPS"
    assert event.alert_key == "cloudwatch_alarm:123456789:ap-northeast-1:p-rds-shuriken_ReadIOPS"
    assert event.resource_type == "rds_instance"
    assert event.resource_name == "shuriken"
    assert event.summary == "CloudWatch alarm triggered"
    assert event.event_time == "2026-04-12T13:05:43Z"


def test_optional_fields_default_to_empty() -> None:
    event = make_event()

    assert event.account_id == ""
    assert event.cluster == ""
    assert event.severity == ""
    assert event.namespace == ""
    assert event.metric_name == ""
    assert event.description == ""
    assert event.raw_text == ""
    assert event.raw_payload == {}


def test_optional_fields_can_be_set() -> None:
    event = make_event(
        account_id="123456789",
        cluster="prod-main",
        severity="critical",
        namespace="AWS/RDS",
        metric_name="ReadIOPS",
        description="Threshold crossed",
        raw_text="alert fired",
        raw_payload={"AlarmName": "p-rds-shuriken_ReadIOPS"},
    )

    assert event.account_id == "123456789"
    assert event.cluster == "prod-main"
    assert event.severity == "critical"
    assert event.namespace == "AWS/RDS"
    assert event.metric_name == "ReadIOPS"
    assert event.description == "Threshold crossed"
    assert event.raw_text == "alert fired"
    assert event.raw_payload == {"AlarmName": "p-rds-shuriken_ReadIOPS"}


def test_raw_payload_default_is_not_shared() -> None:
    a = make_event()
    b = make_event()
    a.raw_payload["key"] = "value"

    assert "key" not in b.raw_payload
