import pytest

from openclaw_foundation.runtime.audit import AuditEvent
from openclaw_foundation.runtime.guards import (
    redact_output,
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
