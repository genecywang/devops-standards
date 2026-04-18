import pytest

from openclaw_foundation.adapters.kubernetes import FakeKubernetesProviderAdapter
from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.tools.kubernetes_deployment_status import KubernetesDeploymentStatusTool
from openclaw_foundation.tools.kubernetes_cronjob_status import KubernetesCronJobStatusTool
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


def make_cronjob_request(namespace: str = "dev") -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-cronjob-001",
        source_product="alert_auto_investigator",
        scope={"environment": "staging", "cluster": "staging-main"},
        input_ref="fixture:cronjob-status",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=30,
            max_output_tokens=256,
        ),
        tool_name="get_cronjob_status",
        target={
            "cluster": "staging-main",
            "namespace": namespace,
            "resource_name": "nightly-backfill",
        },
    )


class FailedJobAdapter(FakeKubernetesProviderAdapter):
    def get_job_status(
        self,
        cluster: str,
        namespace: str,
        job_name: str,
    ) -> dict[str, object]:
        return {
            "job_name": job_name,
            "namespace": namespace,
            "active": 0,
            "succeeded": 0,
            "failed": 1,
            "owner_kind": "CronJob",
            "owner_name": "nightly-backfill",
            "conditions": [
                {
                    "type": "Failed",
                    "status": "True",
                    "reason": "BackoffLimitExceeded",
                    "message": "Job has reached the specified backoff limit.",
                }
            ],
        }


class EmptyCronJobAdapter(FakeKubernetesProviderAdapter):
    def get_cronjob_status(
        self,
        cluster: str,
        namespace: str,
        cronjob_name: str,
    ) -> dict[str, object]:
        return {
            "cronjob_name": cronjob_name,
            "namespace": namespace,
            "schedule": "*/30 * * * *",
            "suspend": False,
            "last_schedule_time": "2026-04-18T02:30:00Z",
            "latest_job_name": None,
            "active": 0,
            "succeeded": 0,
            "failed": 0,
            "conditions": [],
        }


def test_get_job_status_tool_uses_adapter_and_returns_summary() -> None:
    tool = KubernetesJobStatusTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_job_request())

    assert "nightly-backfill-12345" in result.summary
    assert "completed successfully" in result.summary
    assert "completion_time=2026-04-18T01:23:45Z" in result.summary
    assert "owned by cronjob nightly-backfill" in result.summary
    assert len(result.evidence) == 1
    assert result.evidence[0]["succeeded"] == 1
    assert result.evidence[0]["owner_kind"] == "CronJob"
    assert result.evidence[0]["owner_name"] == "nightly-backfill"
    assert result.metadata == {
        "health_state": "healthy",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "Completed",
    }


def test_get_job_status_tool_surfaces_failure_reason_in_summary() -> None:
    tool = KubernetesJobStatusTool(
        adapter=FailedJobAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_job_request())

    assert "job nightly-backfill-12345 failed" in result.summary
    assert "reason=BackoffLimitExceeded" in result.summary
    assert "message=Job has reached the specified backoff limit." in result.summary
    assert "owned by cronjob nightly-backfill" in result.summary
    assert result.metadata == {
        "health_state": "failed",
        "attention_required": True,
        "resource_exists": True,
        "primary_reason": "BackoffLimitExceeded",
    }


class RunningJobAdapter(FakeKubernetesProviderAdapter):
    def get_job_status(
        self,
        cluster: str,
        namespace: str,
        job_name: str,
    ) -> dict[str, object]:
        return {
            "job_name": job_name,
            "namespace": namespace,
            "active": 1,
            "succeeded": 0,
            "failed": 0,
            "owner_kind": None,
            "owner_name": None,
            "conditions": [],
        }


def test_get_job_status_tool_describes_running_job_as_in_progress() -> None:
    tool = KubernetesJobStatusTool(
        adapter=RunningJobAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_job_request())

    assert result.summary == "job nightly-backfill-12345 is still running: active=1"
    assert result.metadata == {
        "health_state": "in_progress",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "Running",
    }


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


def test_get_cronjob_status_tool_uses_adapter_and_returns_summary() -> None:
    tool = KubernetesCronJobStatusTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_cronjob_request())

    assert "cronjob nightly-backfill" in result.summary
    assert 'schedule="*/30 * * * *"' in result.summary
    assert "suspend=false" in result.summary
    assert "last_schedule=2026-04-18T02:30:00Z" in result.summary
    assert "latest job nightly-backfill-12345" in result.summary
    assert "completed successfully" in result.summary
    assert len(result.evidence) == 1
    assert result.evidence[0]["latest_job_name"] == "nightly-backfill-12345"
    assert result.metadata == {
        "health_state": "healthy",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "Completed",
    }


def test_get_cronjob_status_tool_handles_no_recent_jobs() -> None:
    tool = KubernetesCronJobStatusTool(
        adapter=EmptyCronJobAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_cronjob_request())

    assert result.summary == (
        'cronjob nightly-backfill schedule="*/30 * * * *" suspend=false '
        "last_schedule=2026-04-18T02:30:00Z has no recent jobs"
    )
    assert result.metadata == {
        "health_state": "idle",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "NoRecentJobs",
    }


class SuspendedCronJobAdapter(FakeKubernetesProviderAdapter):
    def get_cronjob_status(
        self,
        cluster: str,
        namespace: str,
        cronjob_name: str,
    ) -> dict[str, object]:
        return {
            "cronjob_name": cronjob_name,
            "namespace": namespace,
            "schedule": "*/30 * * * *",
            "suspend": True,
            "last_schedule_time": "2026-04-18T02:30:00Z",
            "latest_job_name": None,
            "active": 0,
            "succeeded": 0,
            "failed": 0,
            "conditions": [],
        }


def test_get_cronjob_status_tool_calls_out_suspended_cronjob() -> None:
    tool = KubernetesCronJobStatusTool(
        adapter=SuspendedCronJobAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_cronjob_request())

    assert result.summary == (
        'cronjob nightly-backfill schedule="*/30 * * * *" suspend=true '
        "last_schedule=2026-04-18T02:30:00Z is suspended; no recent jobs"
    )
    assert result.metadata == {
        "health_state": "suspended",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "Suspended",
    }
