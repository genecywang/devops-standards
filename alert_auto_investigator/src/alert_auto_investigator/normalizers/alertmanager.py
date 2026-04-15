from alert_auto_investigator.models.normalized_alert_event import NormalizedAlertEvent

_STATUS_MAP: dict[str, str] = {
    "firing": "firing",
    "resolved": "resolved",
}


def _infer_resource(labels: dict) -> tuple[str, str]:
    """Return (resource_type, resource_name) from Alertmanager alert labels."""
    if "pod" in labels:
        return "pod", labels["pod"]
    if "deployment" in labels:
        return "deployment", labels["deployment"]
    if "node" in labels:
        return "node", labels["node"]
    if "instance" in labels:
        return "node", labels["instance"]
    return "unknown", "unknown"


def _build_alert_key(cluster: str, namespace: str, alert_name: str, resource_type: str, resource_name: str) -> str:
    if resource_type in {"pod", "deployment"}:
        return f"alertmanager:{cluster}:{namespace}:{alert_name}:{resource_name}"
    return f"alertmanager:{cluster}:{alert_name}:{resource_name}"


def normalize(alert: dict, environment: str, region_code: str) -> NormalizedAlertEvent:
    """Normalize a single Alertmanager alert object into a NormalizedAlertEvent.

    Args:
        alert: One entry from the Alertmanager webhook ``alerts`` array.
        environment: Deployment environment label (e.g. "prod-jp").
        region_code: AWS / GCP region code (e.g. "ap-northeast-1").
    """
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})

    raw_status = alert.get("status", "")
    status = _STATUS_MAP.get(raw_status, "unknown")

    alert_name = labels.get("alertname", "")
    cluster = labels.get("cluster", "")
    namespace = labels.get("namespace", "")
    severity = labels.get("severity", "")

    resource_type, resource_name = _infer_resource(labels)
    alert_key = _build_alert_key(cluster, namespace, alert_name, resource_type, resource_name)

    event_time = alert.get("startsAt", "") if status != "resolved" else alert.get("endsAt", "")

    summary = annotations.get("summary", f"Alertmanager alert: {alert_name}")

    return NormalizedAlertEvent(
        schema_version="v1",
        source="alertmanager",
        status=status,
        environment=environment,
        region_code=region_code,
        alert_name=alert_name,
        alert_key=alert_key,
        resource_type=resource_type,
        resource_name=resource_name,
        summary=summary,
        event_time=event_time,
        cluster=cluster,
        namespace=namespace,
        severity=severity,
        description=annotations.get("description", ""),
        raw_payload=alert,
    )
