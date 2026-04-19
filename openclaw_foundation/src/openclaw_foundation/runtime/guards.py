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
_MAX_LOG_LINES = 100
_MAX_LOG_LINE_LEN = 512
_MAX_TARGET_IPS = 20
_MAX_CONTROLLER_TAG_VALUE_LEN = 256
_TARGET_GROUP_CONTROLLER_TAG_KEYS = (
    "elbv2.k8s.aws/cluster",
    "service.k8s.aws/resource",
    "service.k8s.aws/stack",
)


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


def truncate_job_status(payload: dict[str, object]) -> dict[str, object]:
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


def truncate_rds_instance_status(payload: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in payload.items()
        if key
        in {
            "db_instance_identifier",
            "status",
            "engine",
            "engine_version",
            "instance_class",
            "multi_az",
            "endpoint_address",
            "endpoint_port",
        }
    }


def truncate_target_group_status(payload: dict[str, object]) -> dict[str, object]:
    result = {
        key: value
        for key, value in payload.items()
        if key
        in {
            "target_group_name",
            "target_group_arn",
            "target_type",
            "protocol",
            "port",
            "vpc_id",
            "healthy_count",
            "unhealthy_count",
            "initial_count",
            "draining_count",
            "unused_count",
        }
    }
    target_ips = payload.get("target_ips")
    if isinstance(target_ips, list):
        result["target_ips"] = target_ips[:_MAX_TARGET_IPS]
    controller_tags = payload.get("k8s_controller_tags")
    if isinstance(controller_tags, dict):
        result["k8s_controller_tags"] = {
            key: _truncate_string(str(controller_tags[key]), _MAX_CONTROLLER_TAG_VALUE_LEN)
            for key in _TARGET_GROUP_CONTROLLER_TAG_KEYS
            if key in controller_tags
        }
    return result


def truncate_load_balancer_status(payload: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in payload.items()
        if key
        in {
            "load_balancer_name",
            "load_balancer_arn",
            "dns_name",
            "scheme",
            "type",
            "state",
            "vpc_id",
            "availability_zone_count",
            "security_group_count",
        }
    }


def truncate_pod_logs(lines: list[str]) -> list[str]:
    bounded = lines[:_MAX_LOG_LINES]
    return [
        line[:_MAX_LOG_LINE_LEN] + "...[truncated]" if len(line) > _MAX_LOG_LINE_LEN else line
        for line in bounded
    ]


def redact_log_lines(lines: list[str]) -> list[str]:
    return [_mask_string(line) for line in lines]


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


def _truncate_string(value: str, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    return value[:max_len] + "...[truncated]"
