from __future__ import annotations

from typing import Any, Protocol

try:
    from kubernetes import client, config as kube_config
except ImportError:  # pragma: no cover - exercised via real provider setup
    client = None
    kube_config = None


class KubernetesConfigError(RuntimeError):
    pass


class KubernetesApiError(RuntimeError):
    pass


class KubernetesProviderAdapter(Protocol):
    def get_pod_status(self, cluster: str, namespace: str, pod_name: str) -> dict[str, object]: ...


def build_core_v1_api() -> Any:
    if client is None or kube_config is None:
        raise KubernetesConfigError("kubernetes client dependency is not installed")

    try:
        kube_config.load_incluster_config()
    except Exception:
        try:
            kube_config.load_kube_config()
        except Exception as kubeconfig_error:
            raise KubernetesConfigError("unable to load kubernetes config") from kubeconfig_error

    return client.CoreV1Api()


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


class RealKubernetesProviderAdapter:
    def __init__(self, core_v1_api: Any) -> None:
        self._core_v1_api = core_v1_api

    def get_pod_status(self, cluster: str, namespace: str, pod_name: str) -> dict[str, object]:
        try:
            pod = self._core_v1_api.read_namespaced_pod_status(name=pod_name, namespace=namespace)
        except Exception as error:
            raise KubernetesApiError("failed to read pod status") from error

        statuses = []
        for container_status in getattr(pod.status, "container_statuses", []) or []:
            statuses.append(
                {
                    "name": container_status.name,
                    "ready": container_status.ready,
                    "image": getattr(container_status, "image", None),
                }
            )

        return {
            "pod_name": pod.metadata.name,
            "namespace": namespace,
            "phase": pod.status.phase,
            "container_statuses": statuses,
            "node_name": getattr(pod.spec, "node_name", None),
        }
