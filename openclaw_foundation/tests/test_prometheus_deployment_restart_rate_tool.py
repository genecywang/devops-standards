import pytest

from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.tools.prometheus_deployment_restart_rate import (
    PrometheusDeploymentRestartRateTool,
)


class StubPrometheusAdapter:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def get_deployment_restart_rate(
        self, namespace: str, deployment_name: str
    ) -> dict[str, object]:
        return self.payload


def make_request(namespace: str = "payments") -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-deployment-restart-001",
        source_product="self_service_copilot",
        scope={"environment": "staging", "cluster": "staging-main"},
        input_ref="fixture:deployment-restart-rate",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=15,
            max_output_tokens=256,
        ),
        tool_name="get_deployment_restart_rate",
        target={
            "cluster": "staging-main",
            "namespace": namespace,
            "resource_name": "payments-api",
        },
    )


def test_get_deployment_restart_rate_tool_uses_elevated_summary() -> None:
    payload = {
        "namespace": "payments",
        "deployment_name": "payments-api",
        "recent_restarts_15m": 3,
        "total_restarts": 7,
        "pod_breakdown": [
            {"pod_name": "payments-api-a", "recent_restarts_15m": 2, "total_restarts": 4},
            {"pod_name": "payments-api-b", "recent_restarts_15m": 1, "total_restarts": 3},
        ],
        "pods_shown": 2,
        "pods_total": 2,
        "no_pods": False,
        "window": "15m",
    }
    tool = PrometheusDeploymentRestartRateTool(StubPrometheusAdapter(payload), {"payments"})

    result = tool.invoke(make_request())

    assert "restart activity is elevated" in result.summary
    assert "top pods: payments-api-a (2 recent, 4 total)" in result.summary


def test_get_deployment_restart_rate_tool_uses_quiet_summary() -> None:
    payload = {
        "namespace": "payments",
        "deployment_name": "payments-api",
        "recent_restarts_15m": 0,
        "total_restarts": 7,
        "pod_breakdown": [],
        "pods_shown": 0,
        "pods_total": 2,
        "no_pods": False,
        "window": "15m",
    }
    tool = PrometheusDeploymentRestartRateTool(StubPrometheusAdapter(payload), {"payments"})

    result = tool.invoke(make_request())

    assert "restart activity is quiet" in result.summary
    assert "no pod restart metrics found" in result.summary


def test_get_deployment_restart_rate_tool_includes_truncation_note() -> None:
    payload = {
        "namespace": "payments",
        "deployment_name": "payments-api",
        "recent_restarts_15m": 5,
        "total_restarts": 9,
        "pod_breakdown": [
            {"pod_name": "payments-api-a", "recent_restarts_15m": 3, "total_restarts": 4},
            {"pod_name": "payments-api-b", "recent_restarts_15m": 2, "total_restarts": 3},
        ],
        "pods_shown": 2,
        "pods_total": 6,
        "no_pods": False,
        "window": "15m",
    }
    tool = PrometheusDeploymentRestartRateTool(StubPrometheusAdapter(payload), {"payments"})

    result = tool.invoke(make_request())

    assert "showing 2 of 6" in result.summary


def test_get_deployment_restart_rate_tool_reports_no_pods() -> None:
    payload = {
        "namespace": "payments",
        "deployment_name": "payments-api",
        "recent_restarts_15m": 0,
        "total_restarts": 0,
        "pod_breakdown": [],
        "pods_shown": 0,
        "pods_total": 0,
        "no_pods": True,
        "window": "15m",
    }
    tool = PrometheusDeploymentRestartRateTool(StubPrometheusAdapter(payload), {"payments"})

    result = tool.invoke(make_request())

    assert "no pods found for deployment" in result.summary


def test_get_deployment_restart_rate_tool_denies_disallowed_namespace() -> None:
    payload = {
        "namespace": "payments",
        "deployment_name": "payments-api",
        "recent_restarts_15m": 0,
        "total_restarts": 0,
        "pod_breakdown": [],
        "pods_shown": 0,
        "pods_total": 0,
        "no_pods": True,
        "window": "15m",
    }
    tool = PrometheusDeploymentRestartRateTool(StubPrometheusAdapter(payload), {"payments"})

    with pytest.raises(PermissionError, match="namespace is not allowed"):
        tool.invoke(make_request(namespace="internal"))
