from openclaw_foundation.adapters.kubernetes import (
    FakeKubernetesProviderAdapter,
    KubernetesResourceNotFoundError,
)
from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.tools.kubernetes_deployment_status import KubernetesDeploymentStatusTool
from openclaw_foundation.tools.kubernetes_cronjob_status import KubernetesCronJobStatusTool
from openclaw_foundation.tools.kubernetes_job_status import KubernetesJobStatusTool
from openclaw_foundation.tools.kubernetes_pod_events import KubernetesPodEventsTool


def _make_request(tool_name: str, resource_name: str, namespace: str = "dev") -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id=f"req-{tool_name}",
        source_product="alert_auto_investigator",
        scope={"environment": "staging", "cluster": "staging-main"},
        input_ref=f"fixture:{tool_name}",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=30,
            max_output_tokens=256,
        ),
        tool_name=tool_name,
        target={
            "cluster": "staging-main",
            "namespace": namespace,
            "resource_name": resource_name,
        },
    )


class _DeletedPodAdapter(FakeKubernetesProviderAdapter):
    def get_pod_status(self, cluster: str, namespace: str, pod_name: str) -> dict[str, object]:
        raise KubernetesResourceNotFoundError("pod not found")

    def get_pod_events(self, cluster: str, namespace: str, pod_name: str) -> list[dict[str, object]]:
        return [
            {
                "type": "Normal",
                "reason": "Scheduled",
                "message": f"Successfully assigned {namespace}/{pod_name} to node-a",
                "count": 1,
                "last_timestamp": "2026-04-18T03:00:00Z",
            }
        ]


class _HealthyPodAdapter(FakeKubernetesProviderAdapter):
    def get_pod_status(self, cluster: str, namespace: str, pod_name: str) -> dict[str, object]:
        return {
            "pod_name": pod_name,
            "namespace": namespace,
            "phase": "Running",
            "container_statuses": [
                {
                    "name": "app",
                    "ready": True,
                    "image": "example:v1",
                    "restart_count": 0,
                    "state": {},
                }
            ],
            "node_name": "node-a",
        }

    def get_pod_events(self, cluster: str, namespace: str, pod_name: str) -> list[dict[str, object]]:
        return []


class _FailedJobAdapter(FakeKubernetesProviderAdapter):
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
            "failed": 3,
            "owner_kind": "CronJob",
            "owner_name": "cronjob-iam-user-keyscan",
            "conditions": [
                {
                    "type": "Failed",
                    "status": "True",
                    "reason": "BackoffLimitExceeded",
                    "message": "Job has reached the specified backoff limit.",
                }
            ],
        }


class _HealthyDeploymentAdapter(FakeKubernetesProviderAdapter):
    def get_deployment_status(
        self,
        cluster: str,
        namespace: str,
        deployment_name: str,
    ) -> dict[str, object]:
        return {
            "deployment_name": deployment_name,
            "namespace": namespace,
            "desired_replicas": 3,
            "ready_replicas": 3,
            "available_replicas": 3,
            "updated_replicas": 3,
            "conditions": [
                {
                    "type": "Available",
                    "status": "True",
                    "reason": "MinimumReplicasAvailable",
                    "message": "Deployment has minimum availability.",
                }
            ],
        }


class _DegradedPodAdapter(FakeKubernetesProviderAdapter):
    def get_pod_status(self, cluster: str, namespace: str, pod_name: str) -> dict[str, object]:
        return {
            "pod_name": pod_name,
            "namespace": namespace,
            "phase": "Running",
            "container_statuses": [
                {
                    "name": "app",
                    "ready": True,
                    "image": "example:v1",
                    "restart_count": 4,
                    "state": {
                        "terminated_reason": "OOMKilled",
                        "terminated_exit_code": 137,
                    },
                }
            ],
            "node_name": "node-a",
        }

    def get_pod_events(self, cluster: str, namespace: str, pod_name: str) -> list[dict[str, object]]:
        return []


class _SuspendedCronJobAdapter(FakeKubernetesProviderAdapter):
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


class _IdleCronJobAdapter(FakeKubernetesProviderAdapter):
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


def test_golden_metadata_deleted_pod_contract() -> None:
    tool = KubernetesPodEventsTool(
        adapter=_DeletedPodAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(_make_request("get_pod_events", "worker-pod"))

    assert result.metadata == {
        "health_state": "gone",
        "attention_required": False,
        "resource_exists": False,
        "primary_reason": "Deleted",
    }


def test_golden_metadata_healthy_deployment_contract() -> None:
    tool = KubernetesDeploymentStatusTool(
        adapter=_HealthyDeploymentAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(_make_request("get_deployment_status", "medication-service"))

    assert result.metadata == {
        "health_state": "healthy",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "MinimumReplicasAvailable",
    }


def test_golden_metadata_healthy_pod_contract() -> None:
    tool = KubernetesPodEventsTool(
        adapter=_HealthyPodAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(_make_request("get_pod_events", "dev-py3-h2s-apisvc-7b866db5cd-qfg95"))

    assert result.metadata == {
        "health_state": "healthy",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "Running",
    }


def test_golden_metadata_degraded_pod_contract() -> None:
    tool = KubernetesPodEventsTool(
        adapter=_DegradedPodAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"prod"},
    )

    result = tool.invoke(_make_request("get_pod_events", "prod-h2-server-go-567589445c-n8b9s", namespace="prod"))

    assert result.metadata == {
        "health_state": "degraded",
        "attention_required": True,
        "resource_exists": True,
        "primary_reason": "OOMKilled",
    }


def test_golden_metadata_failed_job_contract() -> None:
    tool = KubernetesJobStatusTool(
        adapter=_FailedJobAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"monitoring"},
    )

    result = tool.invoke(
        _make_request("get_job_status", "cronjob-iam-user-keyscan-manual-86x", namespace="monitoring")
    )

    assert result.metadata == {
        "health_state": "failed",
        "attention_required": True,
        "resource_exists": True,
        "primary_reason": "BackoffLimitExceeded",
    }


def test_golden_metadata_suspended_cronjob_contract() -> None:
    tool = KubernetesCronJobStatusTool(
        adapter=_SuspendedCronJobAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(_make_request("get_cronjob_status", "nightly-backfill"))

    assert result.metadata == {
        "health_state": "suspended",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "Suspended",
    }


def test_golden_metadata_idle_cronjob_contract() -> None:
    tool = KubernetesCronJobStatusTool(
        adapter=_IdleCronJobAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(_make_request("get_cronjob_status", "nightly-backfill"))

    assert result.metadata == {
        "health_state": "idle",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "NoRecentJobs",
    }
