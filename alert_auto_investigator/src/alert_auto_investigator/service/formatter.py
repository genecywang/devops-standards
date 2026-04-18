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
