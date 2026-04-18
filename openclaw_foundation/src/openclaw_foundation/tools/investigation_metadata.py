from __future__ import annotations

HEALTH_STATE_HEALTHY = "healthy"
HEALTH_STATE_DEGRADED = "degraded"
HEALTH_STATE_FAILED = "failed"
HEALTH_STATE_IN_PROGRESS = "in_progress"
HEALTH_STATE_PENDING = "pending"
HEALTH_STATE_IDLE = "idle"
HEALTH_STATE_SUSPENDED = "suspended"
HEALTH_STATE_GONE = "gone"

VALID_HEALTH_STATES = frozenset(
    {
        HEALTH_STATE_HEALTHY,
        HEALTH_STATE_DEGRADED,
        HEALTH_STATE_FAILED,
        HEALTH_STATE_IN_PROGRESS,
        HEALTH_STATE_PENDING,
        HEALTH_STATE_IDLE,
        HEALTH_STATE_SUSPENDED,
        HEALTH_STATE_GONE,
    }
)


def make_investigation_metadata(
    *,
    health_state: str,
    attention_required: bool,
    resource_exists: bool,
    primary_reason: str,
) -> dict[str, object]:
    if health_state not in VALID_HEALTH_STATES:
        raise ValueError(f"unsupported health_state: {health_state}")
    if not primary_reason:
        raise ValueError("primary_reason is required")

    return {
        "health_state": health_state,
        "attention_required": attention_required,
        "resource_exists": resource_exists,
        "primary_reason": primary_reason,
    }
