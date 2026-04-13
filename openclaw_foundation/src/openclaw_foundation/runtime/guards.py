import re
from typing import Any


def validate_scope(
    cluster: str,
    namespace: str,
    allowed_clusters: set[str],
    allowed_namespaces: set[str],
) -> None:
    if not cluster:
        raise ValueError("cluster is required")
    if not namespace:
        raise ValueError("namespace is required")
    if cluster not in allowed_clusters:
        raise PermissionError("cluster is not allowed")
    if namespace not in allowed_namespaces:
        raise PermissionError("namespace is not allowed")


def truncate_pod_status(payload: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in payload.items()
        if key in {"pod_name", "namespace", "phase", "container_statuses", "node_name"}
    }


_MAX_EVENTS = 10
_MAX_MESSAGE_LEN = 256
_MAX_DEPLOYMENT_CONDITIONS = 5
_MAX_CONDITION_MESSAGE_LEN = 256


def truncate_pod_events(events: list[dict[str, object]]) -> list[dict[str, object]]:
    bounded = events[:_MAX_EVENTS]
    result = []
    for event in bounded:
        entry = dict(event)
        msg = entry.get("message")
        if isinstance(msg, str) and len(msg) > _MAX_MESSAGE_LEN:
            entry["message"] = msg[:_MAX_MESSAGE_LEN] + "...[truncated]"
        result.append(entry)
    return result


def truncate_deployment_status(payload: dict[str, object]) -> dict[str, object]:
    result = dict(payload)
    conditions = list(result.get("conditions", []))[:_MAX_DEPLOYMENT_CONDITIONS]
    bounded_conditions = []
    for condition in conditions:
        entry = dict(condition)
        message = entry.get("message")
        if isinstance(message, str) and len(message) > _MAX_CONDITION_MESSAGE_LEN:
            entry["message"] = message[:_MAX_CONDITION_MESSAGE_LEN] + "...[truncated]"
        bounded_conditions.append(entry)
    result["conditions"] = bounded_conditions
    return result


def _mask_string(value: str) -> str:
    patterns = [
        (re.compile(r"Bearer\s+\S+", re.IGNORECASE), "Bearer [REDACTED]"),
        (re.compile(r"password=\S+", re.IGNORECASE), "password=[REDACTED]"),
    ]
    masked = value
    for pattern, replacement in patterns:
        masked = pattern.sub(replacement, masked)
    return masked


def redact_output(payload: dict[str, object]) -> dict[str, object]:
    def redact_value(value: Any) -> Any:
        if isinstance(value, str):
            return _mask_string(value)
        if isinstance(value, dict):
            return {key: redact_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [redact_value(item) for item in value]
        return value

    return {key: redact_value(value) for key, value in payload.items()}
