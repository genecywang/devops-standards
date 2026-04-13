import pytest

from openclaw_foundation.adapters.kubernetes import FakeKubernetesProviderAdapter
from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.tools.kubernetes_deployment_status import KubernetesDeploymentStatusTool


def make_request(namespace: str = "payments") -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-deploy-001",
        source_product="self_service_copilot",
        scope={"environment": "staging", "cluster": "staging-main"},
        input_ref="fixture:deployment-status",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=30,
            max_output_tokens=256,
        ),
        tool_name="get_deployment_status",
        target={
            "cluster": "staging-main",
            "namespace": namespace,
            "resource_name": "payments-api",
        },
    )


def test_get_deployment_status_tool_uses_adapter_and_returns_summary() -> None:
    tool = KubernetesDeploymentStatusTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
    )

    result = tool.invoke(make_request())

    assert "payments-api" in result.summary
    assert len(result.evidence) == 1
    assert result.evidence[0]["desired_replicas"] == 3


def test_get_deployment_status_tool_denies_cluster_outside_allowlist() -> None:
    tool = KubernetesDeploymentStatusTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"prod-main"},
        allowed_namespaces={"payments"},
    )

    with pytest.raises(PermissionError, match="cluster is not allowed"):
        tool.invoke(make_request())


def test_get_deployment_status_tool_redacts_condition_messages() -> None:
    tool = KubernetesDeploymentStatusTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
    )

    result = tool.invoke(make_request())

    all_messages = " ".join(str(c["message"]) for c in result.evidence[0]["conditions"])
    assert "secret-rollout-token" not in all_messages
