import pytest

from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.tools.prometheus_pod_cpu_usage import PrometheusPodCpuUsageTool


class StubPrometheusAdapter:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def get_pod_cpu_usage(self, namespace: str, pod_name: str) -> dict[str, object]:
        return self._payload


def make_request(namespace: str = "dev") -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-pod-cpu-001",
        source_product="self_service_copilot",
        scope={"environment": "staging", "cluster": "staging-main"},
        input_ref="fixture:pod-cpu-usage",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=15,
            max_output_tokens=256,
        ),
        tool_name="get_pod_cpu_usage",
        target={
            "cluster": "staging-main",
            "namespace": namespace,
            "resource_name": "dev-py3-h2s-apisvc-5596c5b6bb-7hrg7",
        },
    )


def test_get_pod_cpu_usage_tool_returns_quiet_summary() -> None:
    tool = PrometheusPodCpuUsageTool(
        adapter=StubPrometheusAdapter(
            {
                "namespace": "dev",
                "pod_name": "dev-py3-h2s-apisvc-5596c5b6bb-7hrg7",
                "avg_cpu_cores_5m": 0.03,
                "window": "5m",
            }
        ),
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_request())

    assert "cpu usage looks quiet" in result.summary
    assert "0.03 cores avg over 5m" in result.summary


def test_get_pod_cpu_usage_tool_returns_hot_summary() -> None:
    tool = PrometheusPodCpuUsageTool(
        adapter=StubPrometheusAdapter(
            {
                "namespace": "dev",
                "pod_name": "dev-py3-h2s-apisvc-5596c5b6bb-7hrg7",
                "avg_cpu_cores_5m": 0.82,
                "window": "5m",
            }
        ),
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_request())

    assert "cpu usage looks hot" in result.summary


def test_get_pod_cpu_usage_tool_denies_namespace_outside_allowlist() -> None:
    tool = PrometheusPodCpuUsageTool(
        adapter=StubPrometheusAdapter(
            {
                "namespace": "dev",
                "pod_name": "dev-py3-h2s-apisvc-5596c5b6bb-7hrg7",
                "avg_cpu_cores_5m": 0.03,
                "window": "5m",
            }
        ),
        allowed_namespaces={"dev"},
    )

    with pytest.raises(PermissionError, match="namespace is not allowed"):
        tool.invoke(make_request(namespace="prod"))
