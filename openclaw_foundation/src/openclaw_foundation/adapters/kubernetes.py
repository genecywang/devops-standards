from typing import Protocol


class KubernetesProviderAdapter(Protocol):
    def get_pod_status(self, cluster: str, namespace: str, pod_name: str) -> dict[str, object]: ...


class FakeKubernetesProviderAdapter:
    def get_pod_status(self, cluster: str, namespace: str, pod_name: str) -> dict[str, object]:
        return {
            "pod_name": pod_name,
            "namespace": namespace,
            "phase": "Running",
            "container_statuses": [
                {
                    "name": "app",
                    "ready": True,
                    "annotation": "Bearer secret-token",
                }
            ],
            "node_name": "node-a",
            "raw_object": {"debug": "drop-me"},
        }
