from __future__ import annotations

from typing import Any, Protocol

try:
    from kubernetes import client, config as kube_config
    from kubernetes.client import ApiException
    from urllib3.exceptions import ConnectTimeoutError, MaxRetryError, NameResolutionError
except ImportError:  # pragma: no cover - exercised via real provider setup
    client = None
    kube_config = None
    ApiException = None
    ConnectTimeoutError = None
    MaxRetryError = None
    NameResolutionError = None


class KubernetesError(RuntimeError):
    pass


class KubernetesConfigError(KubernetesError):
    pass


class KubernetesEndpointUnreachableError(KubernetesError):
    pass


class KubernetesAccessDeniedError(KubernetesError):
    pass


class KubernetesResourceNotFoundError(KubernetesError):
    pass


class KubernetesApiError(KubernetesError):
    pass


class KubernetesProviderAdapter(Protocol):
    def get_pod_status(self, cluster: str, namespace: str, pod_name: str) -> dict[str, object]: ...
    def get_pod_events(self, cluster: str, namespace: str, pod_name: str) -> list[dict[str, object]]: ...


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

    def get_pod_events(self, cluster: str, namespace: str, pod_name: str) -> list[dict[str, object]]:
        return [
            {
                "type": "Warning",
                "reason": "BackOff",
                "message": f"Back-off restarting failed container: Bearer secret-event-token",
                "count": 3,
                "last_timestamp": "2026-04-13T12:00:00Z",
            },
            {
                "type": "Normal",
                "reason": "Pulled",
                "message": "Successfully pulled image example:v1",
                "count": 1,
                "last_timestamp": "2026-04-13T11:55:00Z",
            },
        ]


class RealKubernetesProviderAdapter:
    def __init__(self, core_v1_api: Any) -> None:
        self._core_v1_api = core_v1_api

    def get_pod_status(self, cluster: str, namespace: str, pod_name: str) -> dict[str, object]:
        try:
            pod = self._core_v1_api.read_namespaced_pod_status(name=pod_name, namespace=namespace)
        except ApiException as error:
            if error.status in (401, 403):
                raise KubernetesAccessDeniedError("kubernetes access denied") from error
            if error.status == 404:
                raise KubernetesResourceNotFoundError("pod not found") from error
            raise KubernetesApiError("failed to read pod status") from error
        except (NameResolutionError, ConnectTimeoutError, MaxRetryError) as error:
            raise KubernetesEndpointUnreachableError("cluster endpoint unreachable") from error
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

    def get_pod_events(self, cluster: str, namespace: str, pod_name: str) -> list[dict[str, object]]:
        try:
            event_list = self._core_v1_api.list_namespaced_event(
                namespace=namespace,
                field_selector=f"involvedObject.name={pod_name}",
            )
        except ApiException as error:
            if error.status in (401, 403):
                raise KubernetesAccessDeniedError("kubernetes access denied") from error
            if error.status == 404:
                raise KubernetesResourceNotFoundError("namespace not found") from error
            raise KubernetesApiError("failed to list pod events") from error
        except (NameResolutionError, ConnectTimeoutError, MaxRetryError) as error:
            raise KubernetesEndpointUnreachableError("cluster endpoint unreachable") from error
        except Exception as error:
            raise KubernetesApiError("failed to list pod events") from error

        result = []
        for event in getattr(event_list, "items", []) or []:
            last_ts = getattr(event, "last_timestamp", None)
            result.append(
                {
                    "type": getattr(event, "type", None),
                    "reason": getattr(event, "reason", None),
                    "message": getattr(event, "message", None),
                    "count": getattr(event, "count", None),
                    "last_timestamp": last_ts.isoformat() if last_ts is not None else None,
                }
            )
        return result
