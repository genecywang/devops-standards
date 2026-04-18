import pytest

from openclaw_foundation.adapters.kubernetes import (
    FakeKubernetesProviderAdapter,
    KubernetesResourceNotFoundError,
)
from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.tools.kubernetes_pod_events import KubernetesPodEventsTool


def make_events_request(namespace: str = "dev") -> InvestigationRequest:
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
            "pod_name": "dev-api-123",
        },
    )


class PendingPodAdapter(FakeKubernetesProviderAdapter):
    def get_pod_status(self, cluster: str, namespace: str, pod_name: str) -> dict[str, object]:
        return {
            "pod_name": pod_name,
            "namespace": namespace,
            "phase": "Pending",
            "container_statuses": [
                {
                    "name": "app",
                    "ready": False,
                    "image": "example:v1",
                    "restart_count": 0,
                    "state": {
                        "waiting_reason": "ContainerCreating",
                    },
                }
            ],
            "node_name": "node-a",
        }

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


class DeletedPodAdapter(FakeKubernetesProviderAdapter):
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


def test_get_pod_events_tool_returns_event_list_via_adapter() -> None:
    tool = KubernetesPodEventsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_events_request())

    assert "dev-api-123" in result.summary
    assert len(result.evidence) >= 1
    first = result.evidence[0]
    assert set(first.keys()) == {"type", "reason", "message", "count", "last_timestamp"}


def test_get_pod_events_tool_prioritizes_pod_status_in_summary() -> None:
    tool = KubernetesPodEventsTool(
        adapter=PendingPodAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_events_request())

    assert "pod dev-api-123 is Pending" in result.summary
    assert "waiting reason=ContainerCreating" in result.summary
    assert "latest event=Normal/Scheduled" in result.summary
    assert "needs attention" in result.summary
    assert "has 1 recent events" not in result.summary
    assert result.metadata == {
        "health_state": "degraded",
        "attention_required": True,
        "resource_exists": True,
        "primary_reason": "ContainerCreating",
    }


def test_get_pod_events_tool_degrades_gracefully_when_pod_is_already_deleted() -> None:
    tool = KubernetesPodEventsTool(
        adapter=DeletedPodAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_events_request())

    assert "pod dev-api-123 no longer exists" in result.summary
    assert "latest event=Normal/Scheduled" in result.summary
    assert len(result.evidence) == 1
    assert result.metadata == {
        "health_state": "gone",
        "attention_required": False,
        "resource_exists": False,
        "primary_reason": "Deleted",
    }


class RunningPodAdapter(FakeKubernetesProviderAdapter):
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
        return [
            {
                "type": "Normal",
                "reason": "Scheduled",
                "message": f"Successfully assigned {namespace}/{pod_name} to node-a",
                "count": 1,
                "last_timestamp": "2026-04-18T03:00:00Z",
            }
        ]


class RestartingPodAdapter(FakeKubernetesProviderAdapter):
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


def test_get_pod_events_tool_suppresses_normal_only_event_noise_for_healthy_pod() -> None:
    tool = KubernetesPodEventsTool(
        adapter=RunningPodAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_events_request())

    assert result.summary == "pod dev-api-123 is Running; no recent Warning events"
    assert result.metadata == {
        "health_state": "healthy",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "Running",
    }


def test_get_pod_events_tool_surfaces_restarts_as_actionable_signal() -> None:
    tool = KubernetesPodEventsTool(
        adapter=RestartingPodAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_events_request())

    assert "pod dev-api-123 is Running but needs attention" in result.summary
    assert "last terminated reason=OOMKilled exit_code=137" in result.summary
    assert "restart_count=4" in result.summary
    assert "no recent events" in result.summary
    assert result.metadata == {
        "health_state": "degraded",
        "attention_required": True,
        "resource_exists": True,
        "primary_reason": "OOMKilled",
    }


def test_get_pod_events_tool_denies_cluster_outside_allowlist() -> None:
    tool = KubernetesPodEventsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"prod-main"},
        allowed_namespaces={"dev"},
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
        tool.invoke(make_events_request(namespace="dev"))


def test_get_pod_events_tool_redacts_bearer_token_in_message() -> None:
    tool = KubernetesPodEventsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_events_request())

    all_messages = " ".join(str(e["message"]) for e in result.evidence)
    assert "secret-event-token" not in all_messages
    assert "Bearer [REDACTED]" in all_messages


def test_get_pod_events_tool_evidence_does_not_contain_raw_object() -> None:
    tool = KubernetesPodEventsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_events_request())

    for event in result.evidence:
        assert "raw_object" not in event
        assert "metadata" not in event


def test_get_pod_events_tool_accepts_resource_name_target_key() -> None:
    tool = KubernetesPodEventsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
    )
    request = make_events_request()
    request.target = {
        "cluster": "staging-main",
        "namespace": "dev",
        "resource_name": "dev-api-123",
    }

    result = tool.invoke(request)

    assert "dev-api-123" in result.summary
