import pytest

from openclaw_foundation.adapters.kubernetes import FakeKubernetesProviderAdapter
from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.tools.kubernetes_pod_events import KubernetesPodEventsTool


def make_events_request(namespace: str = "payments") -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-k8s-events-001",
        source_product="alert_auto_investigator",
        scope={"environment": "staging", "cluster": "staging-main"},
        input_ref="fixture:k8s-events-demo",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=30,
            max_output_tokens=256,
        ),
        tool_name="get_pod_events",
        target={
            "cluster": "staging-main",
            "namespace": namespace,
            "pod_name": "payments-api-123",
        },
    )


def test_get_pod_events_tool_returns_event_list_via_adapter() -> None:
    tool = KubernetesPodEventsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
    )

    result = tool.invoke(make_events_request())

    assert "payments-api-123" in result.summary
    assert len(result.evidence) >= 1
    first = result.evidence[0]
    assert set(first.keys()) == {"type", "reason", "message", "count", "last_timestamp"}


def test_get_pod_events_tool_denies_cluster_outside_allowlist() -> None:
    tool = KubernetesPodEventsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"prod-main"},
        allowed_namespaces={"payments"},
    )

    with pytest.raises(PermissionError, match="cluster is not allowed"):
        tool.invoke(make_events_request())


def test_get_pod_events_tool_denies_namespace_outside_allowlist() -> None:
    tool = KubernetesPodEventsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"other"},
    )

    with pytest.raises(PermissionError, match="namespace is not allowed"):
        tool.invoke(make_events_request(namespace="payments"))


def test_get_pod_events_tool_redacts_bearer_token_in_message() -> None:
    tool = KubernetesPodEventsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
    )

    result = tool.invoke(make_events_request())

    all_messages = " ".join(str(e["message"]) for e in result.evidence)
    assert "secret-event-token" not in all_messages
    assert "Bearer [REDACTED]" in all_messages


def test_get_pod_events_tool_evidence_does_not_contain_raw_object() -> None:
    tool = KubernetesPodEventsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
    )

    result = tool.invoke(make_events_request())

    for event in result.evidence:
        assert "raw_object" not in event
        assert "metadata" not in event
