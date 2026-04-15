import pytest

from openclaw_foundation.adapters.prometheus import FakePrometheusProviderAdapter
from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.tools.prometheus_pod_runtime import PrometheusPodRuntimeTool


def make_request(namespace: str = "dev") -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-pod-runtime-001",
        source_product="self_service_copilot",
        scope={"environment": "staging", "cluster": "staging-main"},
        input_ref="fixture:pod-runtime",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=15,
            max_output_tokens=256,
        ),
        tool_name="get_pod_runtime",
        target={
            "cluster": "staging-main",
            "namespace": namespace,
            "resource_name": "dev-py3-h2s-apisvc-5596c5b6bb-7hrg7",
        },
    )


def test_get_pod_runtime_tool_returns_stable_summary() -> None:
    tool = PrometheusPodRuntimeTool(
        adapter=FakePrometheusProviderAdapter(),
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_request())

    assert "runtime looks stable" in result.summary
    assert result.evidence[0]["ready"] is True


def test_get_pod_runtime_tool_denies_namespace_outside_allowlist() -> None:
    tool = PrometheusPodRuntimeTool(
        adapter=FakePrometheusProviderAdapter(),
        allowed_namespaces={"dev"},
    )

    with pytest.raises(PermissionError, match="namespace is not allowed"):
        tool.invoke(make_request(namespace="prod"))
