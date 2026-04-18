from __future__ import annotations

from alert_auto_investigator.models.normalized_alert_event import NormalizedAlertEvent


def format_investigation_reply(event: NormalizedAlertEvent, response: object) -> str:
    result_state = getattr(response, "result_state", "unknown")
    summary = getattr(response, "summary", str(response))
    actions_attempted = getattr(response, "actions_attempted", [])
    metadata = getattr(response, "metadata", {}) or {}
    check = ", ".join(actions_attempted) if actions_attempted else "none"

    lines = [
        "*Investigation Result*",
        f"*Alert:* {event.alert_name}",
        f"*Target:* {event.resource_type}/{event.resource_name}",
        f"*Environment:* {event.environment}",
        f"*Check:* {check}",
        f"*Result:* {result_state}",
    ]
    lines.extend(_format_metadata_lines(metadata))
    lines.append(f"*Summary:* {summary}")
    return "\n".join(lines)


def _format_metadata_lines(metadata: dict[str, object]) -> list[str]:
    if not metadata:
        return []

    compact_lines = _format_compact_metadata_lines(metadata)
    if compact_lines:
        return compact_lines

    lines: list[str] = []

    health_state = metadata.get("health_state")
    if isinstance(health_state, str) and health_state:
        lines.append(f"*Health:* {health_state}")

    if "attention_required" in metadata:
        lines.append(f"*Attention:* {'yes' if bool(metadata['attention_required']) else 'no'}")

    if "resource_exists" in metadata:
        lines.append(f"*Exists:* {'yes' if bool(metadata['resource_exists']) else 'no'}")

    primary_reason = metadata.get("primary_reason")
    if isinstance(primary_reason, str) and primary_reason:
        lines.append(f"*Reason:* {primary_reason}")

    return lines


def _format_compact_metadata_lines(metadata: dict[str, object]) -> list[str]:
    health_state = metadata.get("health_state")
    attention_required = bool(metadata.get("attention_required", False))
    resource_exists = bool(metadata.get("resource_exists", True))
    primary_reason = metadata.get("primary_reason")

    if not isinstance(health_state, str) or not health_state:
        return []
    if not isinstance(primary_reason, str) or not primary_reason:
        return []

    if not resource_exists:
        return [
            f"*State:* {health_state}",
            f"*Reason:* {primary_reason}",
        ]

    if health_state == "healthy" and not attention_required and resource_exists:
        return [
            f"*State:* {health_state}",
            f"*Reason:* {primary_reason}",
        ]

    return []
