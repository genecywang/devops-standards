from alert_auto_investigator.models.normalized_alert_event import NormalizedAlertEvent

_ALERTMANAGER_STATUS_MAP = {
    "firing": "firing",
    "resolved": "resolved",
}
_CLOUDWATCH_STATUS_MAP = {
    "ALARM": "firing",
    "OK": "resolved",
}
_NAMESPACE_KEY_RESOURCE_TYPES = {"pod", "deployment", "service"}
_BLOCK_MARKER = "--- Structured Alert ---"


def _parse_key_value_block(text: str, stop_at: str | None = None) -> dict[str, str]:
    parsed: dict[str, str] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if stop_at is not None and line == stop_at:
            break
        if ":" not in line:
            continue

        key, value = line.split(":", maxsplit=1)
        parsed[key.strip()] = value.strip()

    return parsed


def _build_alertmanager_alert_key(
    cluster: str,
    namespace: str,
    alert_name: str,
    resource_type: str,
    resource_name: str,
) -> str:
    if resource_type in _NAMESPACE_KEY_RESOURCE_TYPES:
        return f"alertmanager:{cluster}:{namespace}:{alert_name}:{resource_name}"
    return f"alertmanager:{cluster}:{alert_name}:{resource_name}"


def parse_alertmanager_slack_message(
    text: str,
    region_code: str,
    fallback_environment: str,
) -> NormalizedAlertEvent | None:
    fields = _parse_key_value_block(text, stop_at="RawLabels:")

    alert_source = fields.get("AlertSource")
    cluster = fields.get("Cluster")
    alert_name = fields.get("AlertName")
    resource_type = fields.get("ResourceType")
    resource_name = fields.get("ResourceName")
    summary = fields.get("Summary")
    namespace = fields.get("Namespace")

    if not all([alert_source, cluster, alert_name, resource_type, resource_name, summary, namespace]):
        return None
    if alert_source != "prometheus":
        return None

    environment = fields.get("Environment", "")
    if environment == "unknown":
        environment = fallback_environment

    status = _ALERTMANAGER_STATUS_MAP.get(fields.get("Status", ""), "unknown")
    if namespace == "-":
        namespace = ""

    return NormalizedAlertEvent(
        schema_version="v1",
        source="alertmanager",
        status=status,
        environment=environment or fallback_environment,
        region_code=region_code,
        alert_name=alert_name,
        alert_key=_build_alertmanager_alert_key(
            cluster=cluster,
            namespace=namespace,
            alert_name=alert_name,
            resource_type=resource_type,
            resource_name=resource_name,
        ),
        resource_type=resource_type,
        resource_name=resource_name,
        summary=summary,
        event_time="",
        cluster=cluster,
        severity=fields.get("Severity", ""),
        namespace=namespace,
        description=fields.get("Description", ""),
        raw_text=text,
    )


def parse_cloudwatch_slack_message(text: str) -> NormalizedAlertEvent | None:
    if _BLOCK_MARKER not in text:
        return None

    _, block = text.split(_BLOCK_MARKER, maxsplit=1)
    fields = _parse_key_value_block(block)

    schema_version = fields.get("schema_version", "")
    source = fields.get("source", "")
    alert_name = fields.get("alert_name", "")
    alert_key = fields.get("alert_key", "")

    if not all([schema_version, source, alert_name, alert_key]):
        return None

    return NormalizedAlertEvent(
        schema_version=schema_version,
        source=source,
        status=_CLOUDWATCH_STATUS_MAP.get(fields.get("status", ""), "unknown"),
        environment=fields.get("environment", ""),
        region_code=fields.get("region_code", ""),
        account_id=fields.get("account_id", ""),
        alert_name=alert_name,
        alert_key=alert_key,
        resource_type=fields.get("resource_type", "unknown"),
        resource_name=fields.get("resource_name", "unknown"),
        summary=f"CloudWatch alarm {fields.get('status', '')}: {alert_name}",
        event_time=fields.get("event_time", ""),
        raw_text=text,
    )
