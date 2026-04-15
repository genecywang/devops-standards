from __future__ import annotations

from alert_auto_investigator.models.normalized_alert_event import NormalizedAlertEvent


def format_investigation_reply(event: NormalizedAlertEvent, response: object) -> str:
    result_state = getattr(response, "result_state", "unknown")
    summary = getattr(response, "summary", str(response))
    actions_attempted = getattr(response, "actions_attempted", [])
    check = ", ".join(actions_attempted) if actions_attempted else "none"

    lines = [
        "*Investigation Result*",
        f"*Alert:* {event.alert_name}",
        f"*Target:* {event.resource_type}/{event.resource_name}",
        f"*Environment:* {event.environment}",
        f"*Check:* {check}",
        f"*Result:* {result_state}",
        f"*Summary:* {summary}",
    ]
    return "\n".join(lines)
