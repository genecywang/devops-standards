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
    def get_pod_logs(self, cluster: str, namespace: str, pod_name: str, tail_lines: int = 100) -> list[str]: ...
    def get_deployment_status(
        self, cluster: str, namespace: str, deployment_name: str
    ) -> dict[str, object]: ...
    def get_job_status(self, cluster: str, namespace: str, job_name: str) -> dict[str, object]: ...


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


def build_apps_v1_api() -> Any:
    if client is None or kube_config is None:
        raise KubernetesConfigError("kubernetes client dependency is not installed")

    try:
        kube_config.load_incluster_config()
    except Exception:
        try:
            kube_config.load_kube_config()
        except Exception as kubeconfig_error:
            raise KubernetesConfigError("unable to load kubernetes config") from kubeconfig_error

    return client.AppsV1Api()


def build_batch_v1_api() -> Any:
    if client is None or kube_config is None:
        raise KubernetesConfigError("kubernetes client dependency is not installed")

    try:
        kube_config.load_incluster_config()
    except Exception:
        try:
            kube_config.load_kube_config()
        except Exception as kubeconfig_error:
            raise KubernetesConfigError("unable to load kubernetes config") from kubeconfig_error

    return client.BatchV1Api()


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

    def get_pod_logs(
        self, cluster: str, namespace: str, pod_name: str, tail_lines: int = 100
    ) -> list[str]:
        return [
            f"2026-04-13T12:00:00Z INFO starting server pod={pod_name}",
            "2026-04-13T12:00:01Z INFO listening on :8080",
            "2026-04-13T12:00:05Z INFO request received method=GET path=/health",
            "2026-04-13T12:00:10Z WARN slow query Authorization: Bearer secret-log-token",
        ]

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
                    "message": "Deployment is available. Bearer secret-rollout-token",
                }
            ],
        }

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
            "succeeded": 1,
            "failed": 0,
            "owner_kind": "CronJob",
            "owner_name": "nightly-backfill",
            "completion_time": "2026-04-18T01:23:45Z",
            "conditions": [
                {
                    "type": "Complete",
                    "status": "True",
                    "reason": "Completed",
                    "message": "Job completed successfully. Bearer secret-job-token",
                }
            ],
        }


class RealKubernetesProviderAdapter:
    def __init__(
        self,
        core_v1_api: Any,
        apps_v1_api: Any | None = None,
        batch_v1_api: Any | None = None,
    ) -> None:
        self._core_v1_api = core_v1_api
        self._apps_v1_api = apps_v1_api
        self._batch_v1_api = batch_v1_api

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

    def get_pod_logs(
        self, cluster: str, namespace: str, pod_name: str, tail_lines: int = 100
    ) -> list[str]:
        try:
            logs: str = self._core_v1_api.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                tail_lines=tail_lines,
            )
        except ApiException as error:
            if error.status in (401, 403):
                raise KubernetesAccessDeniedError("kubernetes access denied") from error
            if error.status == 404:
                raise KubernetesResourceNotFoundError("pod not found") from error
            raise KubernetesApiError("failed to read pod logs") from error
        except (NameResolutionError, ConnectTimeoutError, MaxRetryError) as error:
            raise KubernetesEndpointUnreachableError("cluster endpoint unreachable") from error
        except Exception as error:
            raise KubernetesApiError("failed to read pod logs") from error

        if not logs:
            return []
        return logs.splitlines()

    def get_deployment_status(
        self,
        cluster: str,
        namespace: str,
        deployment_name: str,
    ) -> dict[str, object]:
        if self._apps_v1_api is None:
            raise KubernetesApiError("failed to read deployment status")

        try:
            deployment = self._apps_v1_api.read_namespaced_deployment_status(
                name=deployment_name,
                namespace=namespace,
            )
        except ApiException as error:
            if error.status in (401, 403):
                raise KubernetesAccessDeniedError("kubernetes access denied") from error
            if error.status == 404:
                raise KubernetesResourceNotFoundError("deployment not found") from error
            raise KubernetesApiError("failed to read deployment status") from error
        except (NameResolutionError, ConnectTimeoutError, MaxRetryError) as error:
            raise KubernetesEndpointUnreachableError("cluster endpoint unreachable") from error
        except Exception as error:
            raise KubernetesApiError("failed to read deployment status") from error

        conditions = []
        for condition in getattr(deployment.status, "conditions", []) or []:
            conditions.append(
                {
                    "type": getattr(condition, "type", None),
                    "status": getattr(condition, "status", None),
                    "reason": getattr(condition, "reason", None),
                    "message": getattr(condition, "message", None),
                }
            )

        return {
            "deployment_name": deployment.metadata.name,
            "namespace": namespace,
            "desired_replicas": getattr(deployment.spec, "replicas", 0) or 0,
            "ready_replicas": getattr(deployment.status, "ready_replicas", 0) or 0,
            "available_replicas": getattr(deployment.status, "available_replicas", 0) or 0,
            "updated_replicas": getattr(deployment.status, "updated_replicas", 0) or 0,
            "conditions": conditions,
        }

    def get_job_status(
        self,
        cluster: str,
        namespace: str,
        job_name: str,
    ) -> dict[str, object]:
        if self._batch_v1_api is None:
            raise KubernetesApiError("failed to read job status")

        try:
            job = self._batch_v1_api.read_namespaced_job_status(
                name=job_name,
                namespace=namespace,
            )
        except ApiException as error:
            if error.status in (401, 403):
                raise KubernetesAccessDeniedError("kubernetes access denied") from error
            if error.status == 404:
                raise KubernetesResourceNotFoundError("job not found") from error
            raise KubernetesApiError("failed to read job status") from error
        except (NameResolutionError, ConnectTimeoutError, MaxRetryError) as error:
            raise KubernetesEndpointUnreachableError("cluster endpoint unreachable") from error
        except Exception as error:
            raise KubernetesApiError("failed to read job status") from error

        conditions = []
        for condition in getattr(job.status, "conditions", []) or []:
            conditions.append(
                {
                    "type": getattr(condition, "type", None),
                    "status": getattr(condition, "status", None),
                    "reason": getattr(condition, "reason", None),
                    "message": getattr(condition, "message", None),
                }
            )

        owner_kind = None
        owner_name = None
        owner_references = getattr(job.metadata, "owner_references", []) or []
        for owner_reference in owner_references:
            if getattr(owner_reference, "controller", False):
                owner_kind = getattr(owner_reference, "kind", None)
                owner_name = getattr(owner_reference, "name", None)
                break
        if owner_kind is None and owner_references:
            owner_kind = getattr(owner_references[0], "kind", None)
            owner_name = getattr(owner_references[0], "name", None)

        completion_time = getattr(job.status, "completion_time", None)
        return {
            "job_name": job.metadata.name,
            "namespace": namespace,
            "active": getattr(job.status, "active", 0) or 0,
            "succeeded": getattr(job.status, "succeeded", 0) or 0,
            "failed": getattr(job.status, "failed", 0) or 0,
            "owner_kind": owner_kind,
            "owner_name": owner_name,
            "completion_time": completion_time.isoformat() if completion_time is not None else None,
            "conditions": conditions,
        }
