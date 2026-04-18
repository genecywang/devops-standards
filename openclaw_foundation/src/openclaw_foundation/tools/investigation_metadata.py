from __future__ import annotations


def make_investigation_metadata(
    *,
    health_state: str,
    attention_required: bool,
    resource_exists: bool,
    primary_reason: str,
) -> dict[str, object]:
    return {
        "health_state": health_state,
        "attention_required": attention_required,
        "resource_exists": resource_exists,
        "primary_reason": primary_reason,
    }
