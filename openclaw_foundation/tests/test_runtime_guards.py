import pytest

from openclaw_foundation.runtime.audit import AuditEvent
from openclaw_foundation.runtime.guards import (
    redact_output,
    truncate_pod_events,
    truncate_pod_status,
    validate_scope,
)


def test_validate_scope_rejects_missing_cluster() -> None:
    with pytest.raises(ValueError, match="cluster is required"):
        validate_scope(
            cluster="",
            namespace="payments",
            allowed_clusters={"staging-main"},
            allowed_namespaces={"payments"},
        )


def test_validate_scope_rejects_namespace_outside_allowlist() -> None:
    with pytest.raises(PermissionError, match="namespace is not allowed"):
        validate_scope(
            cluster="staging-main",
            namespace="forbidden",
            allowed_clusters={"staging-main"},
            allowed_namespaces={"payments"},
        )


def test_truncate_output_drops_unbounded_fields() -> None:
    payload = {
        "pod_name": "payments-api-123",
        "namespace": "payments",
        "phase": "Running",
        "container_statuses": [{"name": "app", "ready": True}],
        "node_name": "node-a",
        "raw_object": {"a": "b"},
    }

    truncated = truncate_pod_status(payload)

    assert "raw_object" not in truncated
    assert truncated["pod_name"] == "payments-api-123"


def test_redact_output_masks_sensitive_values() -> None:
    payload = {
        "annotation": "Bearer secret-token",
        "env_hint": "password=supersecret",
    }

    redacted = redact_output(payload)

    assert "secret-token" not in redacted["annotation"]
    assert "supersecret" not in redacted["env_hint"]


def _make_event(reason: str = "Reason", message: str = "msg") -> dict:
    return {
        "type": "Normal",
        "reason": reason,
        "message": message,
        "count": 1,
        "last_timestamp": "2026-04-13T12:00:00Z",
    }


def test_truncate_pod_events_limits_list_to_ten_events() -> None:
    events = [_make_event(reason=f"R{i}") for i in range(15)]

    result = truncate_pod_events(events)

    assert len(result) == 10


def test_truncate_pod_events_truncates_message_longer_than_256_chars() -> None:
    long_msg = "x" * 300
    events = [_make_event(message=long_msg)]

    result = truncate_pod_events(events)

    assert len(result[0]["message"]) <= 270  # 256 + len("...[truncated]")
    assert result[0]["message"].endswith("...[truncated]")


def test_truncate_pod_events_preserves_short_message_unchanged() -> None:
    events = [_make_event(message="short message")]

    result = truncate_pod_events(events)

    assert result[0]["message"] == "short message"


def test_audit_event_captures_canonical_fields() -> None:
    event = AuditEvent(
        request_id="req-001",
        tool_name="get_pod_status",
        cluster="staging-main",
        namespace="payments",
        result_state="success",
    )

    assert event.request_id == "req-001"
    assert event.tool_name == "get_pod_status"
