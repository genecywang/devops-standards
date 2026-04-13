import pytest

from openclaw_foundation.adapters.kubernetes import FakeKubernetesProviderAdapter
from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.tools.kubernetes_pod_status import KubernetesPodStatusTool


def make_kubernetes_request(namespace: str = "payments") -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-k8s-001",
        source_product="alert_auto_investigator",
        scope={"environment": "staging", "cluster": "staging-main"},
        input_ref="fixture:k8s-demo",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=30,
            max_output_tokens=256,
        ),
        tool_name="get_pod_status",
        target={
            "cluster": "staging-main",
            "namespace": namespace,
            "pod_name": "payments-api-123",
        },
    )


def test_get_pod_status_tool_uses_adapter_and_returns_minimal_payload() -> None:
    tool = KubernetesPodStatusTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
    )

    result = tool.invoke(make_kubernetes_request())

    assert "payments-api-123" in result.summary
    assert result.evidence[0]["phase"] == "Running"
    assert "raw_object" not in result.evidence[0]


def test_get_pod_status_denies_cluster_outside_allowlist() -> None:
    tool = KubernetesPodStatusTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"prod-main"},
        allowed_namespaces={"payments"},
    )

    with pytest.raises(PermissionError, match="cluster is not allowed"):
        tool.invoke(make_kubernetes_request())


def test_get_pod_status_redacts_sensitive_annotation_values() -> None:
    tool = KubernetesPodStatusTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
    )

    result = tool.invoke(make_kubernetes_request())

    assert "secret-token" not in str(result.evidence[0])


def test_get_pod_status_accepts_resource_name_target_key() -> None:
    tool = KubernetesPodStatusTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
    )
    request = make_kubernetes_request()
    request.target = {
        "cluster": "staging-main",
        "namespace": "payments",
        "resource_name": "payments-api-123",
    }

    result = tool.invoke(request)

    assert "payments-api-123" in result.summary
