from alert_auto_investigator.models.normalized_alert_event import NormalizedAlertEvent

# CloudWatch uses AWS-specific Dimension names; normalize them into stable internal
# resource_type values here so the rest of the pipeline does not depend on source field names.
_DIMENSION_TO_RESOURCE_TYPE: dict[str, str] = {
    "DBInstanceIdentifier": "rds_instance",
    "InstanceId": "ec2_instance",
    "LoadBalancer": "load_balancer",
    "ClusterName": "eks_cluster",
}

_STATE_TO_STATUS: dict[str, str] = {
    "ALARM": "firing",
    "OK": "resolved",
}


def normalize(payload: dict, environment: str) -> NormalizedAlertEvent:
    alarm_arn = payload.get("AlarmArn", "")
    arn_parts = alarm_arn.split(":")
    region_code = arn_parts[3] if len(arn_parts) > 3 else ""

    account_id = payload.get("AWSAccountId", "")
    alarm_name = payload.get("AlarmName", "")

    raw_state = payload.get("NewStateValue", "")
    status = _STATE_TO_STATUS.get(raw_state, "unknown")

    trigger = payload.get("Trigger", {})
    dimensions = trigger.get("Dimensions", [])

    resource_type = "unknown"
    resource_name = "unknown"
    for dim in dimensions:
        dim_name = dim.get("name", "")
        if dim_name in _DIMENSION_TO_RESOURCE_TYPE:
            resource_type = _DIMENSION_TO_RESOURCE_TYPE[dim_name]
            resource_name = dim.get("value", "unknown")
            break

    alert_key = f"cloudwatch_alarm:{account_id}:{region_code}:{alarm_name}"

    return NormalizedAlertEvent(
        schema_version="v1",
        source="cloudwatch_alarm",
        status=status,
        environment=environment,
        region_code=region_code,
        account_id=account_id,
        alert_name=alarm_name,
        alert_key=alert_key,
        resource_type=resource_type,
        resource_name=resource_name,
        summary=f"CloudWatch alarm {raw_state}: {alarm_name}",
        event_time=payload.get("StateChangeTime", ""),
        namespace=trigger.get("Namespace", ""),
        metric_name=trigger.get("MetricName", ""),
        description=payload.get("NewStateReason", ""),
        raw_payload=payload,
    )
