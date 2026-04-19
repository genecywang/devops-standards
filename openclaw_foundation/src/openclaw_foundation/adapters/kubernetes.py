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


def _build_exception_type_tuple(*exception_types: object) -> tuple[type[BaseException], ...]:
    return tuple(
        exception_type
        for exception_type in exception_types
        if isinstance(exception_type, type) and issubclass(exception_type, BaseException)
    )


_API_EXCEPTION_TYPES = _build_exception_type_tuple(ApiException)
_ENDPOINT_UNREACHABLE_EXCEPTION_TYPES = _build_exception_type_tuple(
    NameResolutionError,
    ConnectTimeoutError,
    MaxRetryError,
)


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
    def get_cronjob_status(self, cluster: str, namespace: str, cronjob_name: str) -> dict[str, object]: ...
    def find_pod_by_ip(
        self, cluster: str, namespaces: list[str], pod_ip: str
    ) -> dict[str, object] | None: ...
    def find_service_for_pod(
        self, cluster: str, namespaces: list[str], namespace: str, pod_name: str
    ) -> dict[str, object] | None: ...


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


def build_discovery_v1_api() -> Any:
    if client is None or kube_config is None:
        raise KubernetesConfigError("kubernetes client dependency is not installed")

    try:
        kube_config.load_incluster_config()
    except Exception:
        try:
            kube_config.load_kube_config()
        except Exception as kubeconfig_error:
            raise KubernetesConfigError("unable to load kubernetes config") from kubeconfig_error

    return client.DiscoveryV1Api()


class FakeKubernetesProviderAdapter:
    _POD_LOOKUP_FIXTURES = {
        "10.0.1.23": {
            "namespace": "dev",
            "pod_name": "dev-api-123",
        },
        "10.0.2.23": {
            "namespace": "staging",
            "pod_name": "staging-api-123",
        },
    }
    _SERVICE_LOOKUP_FIXTURES = {
        ("dev", "dev-api-123"): {
            "namespace": "dev",
            "service_name": "dev-api",
        },
        ("staging", "staging-api-123"): {
            "namespace": "staging",
            "service_name": "staging-api",
        },
    }
    _SERVICE_LOOKUP_AMBIGUOUS_FIXTURES = {
        ("staging", "staging-api-ambiguous"),
    }

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
                    "restart_count": 0,
                    "state": {},
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
            "latest_job_name": f"{cronjob_name}-12345",
            "active": 0,
            "succeeded": 1,
            "failed": 0,
            "conditions": [
                {
                    "type": "Complete",
                    "status": "True",
                    "reason": "Completed",
                    "message": "Job completed successfully. Bearer secret-cronjob-token",
                }
            ],
        }

    def find_pod_by_ip(
        self,
        cluster: str,
        namespaces: list[str],
        pod_ip: str,
    ) -> dict[str, object] | None:
        fixture = self._POD_LOOKUP_FIXTURES.get(pod_ip)
        if fixture is None:
            return None
        namespace = str(fixture["namespace"])
        if namespace not in namespaces:
            return None
        return {
            "namespace": namespace,
            "pod_name": str(fixture["pod_name"]),
            "pod_ip": pod_ip,
        }

    def find_service_for_pod(
        self,
        cluster: str,
        namespaces: list[str],
        namespace: str,
        pod_name: str,
    ) -> dict[str, object] | None:
        if namespace not in namespaces:
            return None
        lookup_key = (namespace, pod_name)
        if lookup_key in self._SERVICE_LOOKUP_AMBIGUOUS_FIXTURES:
            return None
        fixture = self._SERVICE_LOOKUP_FIXTURES.get(lookup_key)
        if fixture is None:
            return None
        return {
            "namespace": str(fixture["namespace"]),
            "service_name": str(fixture["service_name"]),
        }


class RealKubernetesProviderAdapter:
    def __init__(
        self,
        core_v1_api: Any,
        apps_v1_api: Any | None = None,
        batch_v1_api: Any | None = None,
        discovery_v1_api: Any | None = None,
    ) -> None:
        self._core_v1_api = core_v1_api
        self._apps_v1_api = apps_v1_api
        self._batch_v1_api = batch_v1_api
        self._discovery_v1_api = discovery_v1_api

    def get_pod_status(self, cluster: str, namespace: str, pod_name: str) -> dict[str, object]:
        try:
            pod = self._core_v1_api.read_namespaced_pod_status(name=pod_name, namespace=namespace)
        except _API_EXCEPTION_TYPES as error:
            if error.status in (401, 403):
                raise KubernetesAccessDeniedError("kubernetes access denied") from error
            if error.status == 404:
                raise KubernetesResourceNotFoundError("pod not found") from error
            raise KubernetesApiError("failed to read pod status") from error
        except _ENDPOINT_UNREACHABLE_EXCEPTION_TYPES as error:
            raise KubernetesEndpointUnreachableError("cluster endpoint unreachable") from error
        except Exception as error:
            raise KubernetesApiError("failed to read pod status") from error

        statuses = []
        for container_status in getattr(pod.status, "container_statuses", []) or []:
            state = getattr(container_status, "state", None)
            waiting = getattr(state, "waiting", None) if state is not None else None
            terminated = getattr(state, "terminated", None) if state is not None else None

            normalized_state: dict[str, object] = {}
            if waiting is not None and getattr(waiting, "reason", None):
                normalized_state["waiting_reason"] = waiting.reason
            if waiting is not None and getattr(waiting, "message", None):
                normalized_state["waiting_message"] = waiting.message
            if terminated is not None and getattr(terminated, "reason", None):
                normalized_state["terminated_reason"] = terminated.reason
            if terminated is not None and getattr(terminated, "message", None):
                normalized_state["terminated_message"] = terminated.message
            if terminated is not None and getattr(terminated, "exit_code", None) is not None:
                normalized_state["terminated_exit_code"] = terminated.exit_code

            statuses.append(
                {
                    "name": container_status.name,
                    "ready": container_status.ready,
                    "image": getattr(container_status, "image", None),
                    "restart_count": getattr(container_status, "restart_count", 0),
                    "state": normalized_state,
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
        except _API_EXCEPTION_TYPES as error:
            if error.status in (401, 403):
                raise KubernetesAccessDeniedError("kubernetes access denied") from error
            if error.status == 404:
                raise KubernetesResourceNotFoundError("namespace not found") from error
            raise KubernetesApiError("failed to list pod events") from error
        except _ENDPOINT_UNREACHABLE_EXCEPTION_TYPES as error:
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
        except _API_EXCEPTION_TYPES as error:
            if error.status in (401, 403):
                raise KubernetesAccessDeniedError("kubernetes access denied") from error
            if error.status == 404:
                raise KubernetesResourceNotFoundError("pod not found") from error
            raise KubernetesApiError("failed to read pod logs") from error
        except _ENDPOINT_UNREACHABLE_EXCEPTION_TYPES as error:
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
        except _API_EXCEPTION_TYPES as error:
            if error.status in (401, 403):
                raise KubernetesAccessDeniedError("kubernetes access denied") from error
            if error.status == 404:
                raise KubernetesResourceNotFoundError("deployment not found") from error
            raise KubernetesApiError("failed to read deployment status") from error
        except _ENDPOINT_UNREACHABLE_EXCEPTION_TYPES as error:
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
        except _API_EXCEPTION_TYPES as error:
            if error.status in (401, 403):
                raise KubernetesAccessDeniedError("kubernetes access denied") from error
            if error.status == 404:
                raise KubernetesResourceNotFoundError("job not found") from error
            raise KubernetesApiError("failed to read job status") from error
        except _ENDPOINT_UNREACHABLE_EXCEPTION_TYPES as error:
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

    def get_cronjob_status(
        self,
        cluster: str,
        namespace: str,
        cronjob_name: str,
    ) -> dict[str, object]:
        if self._batch_v1_api is None:
            raise KubernetesApiError("failed to read cronjob status")

        try:
            cronjob = self._batch_v1_api.read_namespaced_cron_job_status(
                name=cronjob_name,
                namespace=namespace,
            )
            job_list = self._batch_v1_api.list_namespaced_job(namespace=namespace)
        except _API_EXCEPTION_TYPES as error:
            if error.status in (401, 403):
                raise KubernetesAccessDeniedError("kubernetes access denied") from error
            if error.status == 404:
                raise KubernetesResourceNotFoundError("namespace not found") from error
            raise KubernetesApiError("failed to read cronjob status") from error
        except _ENDPOINT_UNREACHABLE_EXCEPTION_TYPES as error:
            raise KubernetesEndpointUnreachableError("cluster endpoint unreachable") from error
        except Exception as error:
            raise KubernetesApiError("failed to read cronjob status") from error

        owned_jobs = []
        for job in getattr(job_list, "items", []) or []:
            owner_references = getattr(job.metadata, "owner_references", []) or []
            for owner_reference in owner_references:
                if (
                    getattr(owner_reference, "kind", None) == "CronJob"
                    and getattr(owner_reference, "name", None) == cronjob_name
                ):
                    owned_jobs.append(job)
                    break

        if not owned_jobs:
            return {
                "cronjob_name": cronjob_name,
                "namespace": namespace,
                "schedule": getattr(cronjob.spec, "schedule", None),
                "suspend": bool(getattr(cronjob.spec, "suspend", False)),
                "last_schedule_time": (
                    cronjob.status.last_schedule_time.isoformat()
                    if getattr(cronjob.status, "last_schedule_time", None) is not None
                    else None
                ),
                "latest_job_name": None,
                "active": 0,
                "succeeded": 0,
                "failed": 0,
                "conditions": [],
            }

        latest_job = max(owned_jobs, key=_job_sort_key)
        latest_payload = self.get_job_status(cluster, namespace, latest_job.metadata.name)
        return {
            "cronjob_name": cronjob_name,
            "namespace": namespace,
            "schedule": getattr(cronjob.spec, "schedule", None),
            "suspend": bool(getattr(cronjob.spec, "suspend", False)),
            "last_schedule_time": (
                cronjob.status.last_schedule_time.isoformat()
                if getattr(cronjob.status, "last_schedule_time", None) is not None
                else None
            ),
            "latest_job_name": latest_payload["job_name"],
            "active": latest_payload["active"],
            "succeeded": latest_payload["succeeded"],
            "failed": latest_payload["failed"],
            "conditions": latest_payload["conditions"],
        }

    def find_pod_by_ip(
        self,
        cluster: str,
        namespaces: list[str],
        pod_ip: str,
    ) -> dict[str, object] | None:
        if self._core_v1_api is None:
            raise KubernetesApiError("failed to find pod by ip")

        matches: list[dict[str, object]] = []
        try:
            for namespace in namespaces:
                pod_list = self._core_v1_api.list_namespaced_pod(
                    namespace=namespace,
                    field_selector=f"status.podIP={pod_ip}",
                )
                for pod in getattr(pod_list, "items", []) or []:
                    status = getattr(pod, "status", None)
                    pod_ip_value = getattr(status, "pod_ip", None)
                    if pod_ip_value is None:
                        pod_ip_value = getattr(status, "podIP", None)
                    if pod_ip_value != pod_ip:
                        continue

                    metadata = getattr(pod, "metadata", None)
                    matches.append(
                        {
                            "namespace": getattr(metadata, "namespace", namespace),
                            "pod_name": getattr(metadata, "name", None),
                            "pod_ip": pod_ip_value,
                        }
                    )
        except _API_EXCEPTION_TYPES as error:
            if error.status in (401, 403):
                raise KubernetesAccessDeniedError("kubernetes access denied") from error
            if error.status == 404:
                raise KubernetesResourceNotFoundError("namespace not found") from error
            raise KubernetesApiError("failed to find pod by ip") from error
        except _ENDPOINT_UNREACHABLE_EXCEPTION_TYPES as error:
            raise KubernetesEndpointUnreachableError("cluster endpoint unreachable") from error
        except Exception as error:
            raise KubernetesApiError("failed to find pod by ip") from error

        if len(matches) != 1:
            return None
        return matches[0]

    def find_service_for_pod(
        self,
        cluster: str,
        namespaces: list[str],
        namespace: str,
        pod_name: str,
    ) -> dict[str, object] | None:
        if namespace not in namespaces:
            return None
        discovery_v1_api = self._discovery_v1_api
        if discovery_v1_api is None:
            raise KubernetesApiError("failed to find service for pod")

        try:
            endpoint_slice_list = discovery_v1_api.list_namespaced_endpoint_slice(namespace=namespace)
        except _API_EXCEPTION_TYPES as error:
            if error.status in (401, 403):
                raise KubernetesAccessDeniedError("kubernetes access denied") from error
            if error.status == 404:
                raise KubernetesResourceNotFoundError("namespace not found") from error
            raise KubernetesApiError("failed to find service for pod") from error
        except _ENDPOINT_UNREACHABLE_EXCEPTION_TYPES as error:
            raise KubernetesEndpointUnreachableError("cluster endpoint unreachable") from error
        except Exception as error:
            raise KubernetesApiError("failed to find service for pod") from error

        service_names = set()
        for endpoint_slice in getattr(endpoint_slice_list, "items", []) or []:
            metadata = getattr(endpoint_slice, "metadata", None)
            labels = getattr(metadata, "labels", None) or {}
            service_name = labels.get("kubernetes.io/service-name")
            if not service_name:
                continue

            for endpoint in getattr(endpoint_slice, "endpoints", []) or []:
                target_ref = getattr(endpoint, "target_ref", None)
                if getattr(target_ref, "kind", None) == "Pod" and getattr(target_ref, "name", None) == pod_name:
                    service_names.add(service_name)
                    break

        if len(service_names) != 1:
            return None

        service_name = next(iter(service_names))
        return {
            "namespace": namespace,
            "service_name": service_name,
        }


def _job_sort_key(job: Any) -> tuple[str, str]:
    status = getattr(job, "status", None)
    metadata = getattr(job, "metadata", None)

    start_time = getattr(status, "start_time", None)
    completion_time = getattr(status, "completion_time", None)
    creation_timestamp = getattr(metadata, "creation_timestamp", None)

    start_value = start_time.isoformat() if start_time is not None else ""
    completion_value = completion_time.isoformat() if completion_time is not None else ""
    creation_value = creation_timestamp.isoformat() if creation_timestamp is not None else ""
    return (start_value or completion_value or creation_value, creation_value)
