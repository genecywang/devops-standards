import pytest

from openclaw_foundation.adapters.kubernetes import FakeKubernetesProviderAdapter
from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.tools.kubernetes_deployment_status import KubernetesDeploymentStatusTool
from openclaw_foundation.tools.kubernetes_job_status import KubernetesJobStatusTool
from openclaw_foundation.tools.kubernetes_pod_events import KubernetesPodEventsTool


def make_request(namespace: str = "dev") -> InvestigationRequest:
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
            "resource_name": "dev-api",
        },
    )


def make_pod_request(namespace: str = "dev") -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-pod-events-001",
        source_product="alert_auto_investigator",
        scope={"environment": "staging", "cluster": "staging-main"},
        input_ref="fixture:pod-events",
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
            "resource_name": "dev-api-123",
        },
    )


def test_get_pod_events_tool_returns_actionable_warning_summary() -> None:
    tool = KubernetesPodEventsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_pod_request())

    assert "Warning events" in result.summary
    assert "BackOff x3" in result.summary
    assert "latest reason=BackOff" in result.summary
    assert len(result.evidence) == 2


def test_get_deployment_status_tool_uses_adapter_and_returns_summary() -> None:
    tool = KubernetesDeploymentStatusTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_request())

    assert "dev-api" in result.summary
    assert len(result.evidence) == 1
    assert result.evidence[0]["desired_replicas"] == 3


def test_get_deployment_status_tool_denies_cluster_outside_allowlist() -> None:
    tool = KubernetesDeploymentStatusTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"prod-main"},
        allowed_namespaces={"dev"},
    )

    with pytest.raises(PermissionError, match="cluster is not allowed"):
        tool.invoke(make_request())


def test_get_deployment_status_tool_redacts_condition_messages() -> None:
    tool = KubernetesDeploymentStatusTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_request())

    all_messages = " ".join(str(c["message"]) for c in result.evidence[0]["conditions"])
    assert "secret-rollout-token" not in all_messages


def make_job_request(namespace: str = "dev") -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-job-001",
        source_product="alert_auto_investigator",
        scope={"environment": "staging", "cluster": "staging-main"},
        input_ref="fixture:job-status",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=30,
            max_output_tokens=256,
        ),
        tool_name="get_job_status",
        target={
            "cluster": "staging-main",
            "namespace": namespace,
            "resource_name": "nightly-backfill-12345",
        },
    )


def test_get_job_status_tool_uses_adapter_and_returns_summary() -> None:
    tool = KubernetesJobStatusTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_job_request())

    assert "nightly-backfill-12345" in result.summary
    assert "succeeded" in result.summary
    assert "owned by cronjob nightly-backfill" in result.summary
    assert len(result.evidence) == 1
    assert result.evidence[0]["succeeded"] == 1
    assert result.evidence[0]["owner_kind"] == "CronJob"
    assert result.evidence[0]["owner_name"] == "nightly-backfill"


def test_get_job_status_tool_denies_cluster_outside_allowlist() -> None:
    tool = KubernetesJobStatusTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"prod-main"},
        allowed_namespaces={"dev"},
    )

    with pytest.raises(PermissionError, match="cluster is not allowed"):
        tool.invoke(make_job_request())


def test_get_job_status_tool_redacts_condition_messages() -> None:
    tool = KubernetesJobStatusTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_job_request())

    all_messages = " ".join(str(c["message"]) for c in result.evidence[0]["conditions"])
    assert "secret-job-token" not in all_messages
