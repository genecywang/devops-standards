from __future__ import annotations


def control_reason_code(reason: str) -> str:
    if reason == "all checks passed":
        return "passed"
    if reason == "missing alert_key":
        return "missing_alert_key"
    if reason == "status is resolved":
        return "resolved"
    if reason == "status is unknown":
        return "unknown_status"
    if "is not owned" in reason:
        return "environment_not_owned"
    if "is in denylist" in reason:
        return "denylist"
    if "is not in allowlist" in reason:
        return "allowlist"
    if "is in cooldown" in reason:
        return "cooldown"
    if reason.startswith("rate limit exceeded"):
        return "rate_limit"
    return "other"
