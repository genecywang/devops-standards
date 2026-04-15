import pytest

from openclaw_foundation.adapters.kubernetes import FakeKubernetesProviderAdapter
from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.tools.kubernetes_pod_logs import KubernetesPodLogsTool


def make_logs_request(namespace: str = "dev") -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-k8s-logs-001",
        source_product="self_service_copilot",
        scope={"environment": "staging", "cluster": "staging-main"},
        input_ref="fixture:k8s-logs-demo",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=30,
            max_output_tokens=1024,
        ),
        tool_name="get_pod_logs",
        target={
            "cluster": "staging-main",
            "namespace": namespace,
            "resource_name": "dev-api-123",
        },
    )


def test_get_pod_logs_tool_returns_log_lines_in_summary() -> None:
    tool = KubernetesPodLogsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_logs_request())

    assert "dev-api-123" in result.summary
    assert "log lines" in result.summary
    assert len(result.evidence) >= 1
    assert "line" in result.evidence[0]


def test_get_pod_logs_tool_denies_cluster_outside_allowlist() -> None:
    tool = KubernetesPodLogsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"prod-main"},
        allowed_namespaces={"dev"},
    )

    with pytest.raises(PermissionError, match="cluster is not allowed"):
        tool.invoke(make_logs_request())


def test_get_pod_logs_tool_denies_namespace_outside_allowlist() -> None:
    tool = KubernetesPodLogsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"other"},
    )

    with pytest.raises(PermissionError, match="namespace is not allowed"):
        tool.invoke(make_logs_request(namespace="dev"))


def test_get_pod_logs_tool_redacts_bearer_token_in_log_lines() -> None:
    tool = KubernetesPodLogsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_logs_request())

    all_lines = " ".join(e["line"] for e in result.evidence)
    assert "secret-log-token" not in all_lines
    assert "Bearer [REDACTED]" in all_lines


def test_get_pod_logs_tool_accepts_pod_name_target_key() -> None:
    tool = KubernetesPodLogsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )
    request = make_logs_request()
    request.target = {
        "cluster": "staging-main",
        "namespace": "dev",
        "pod_name": "dev-api-123",
    }

    result = tool.invoke(request)

    assert "dev-api-123" in result.summary


def test_get_pod_logs_tool_returns_no_logs_summary_for_empty_result() -> None:
    class EmptyLogAdapter:
        def get_pod_logs(self, cluster, namespace, pod_name, tail_lines=100):
            return []

    tool = KubernetesPodLogsTool(
        adapter=EmptyLogAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_logs_request())

    assert "no recent logs" in result.summary
    assert result.evidence == []
