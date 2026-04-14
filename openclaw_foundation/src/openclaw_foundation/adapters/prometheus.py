from __future__ import annotations

import json
import logging
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

logger = logging.getLogger(__name__)


class PrometheusError(RuntimeError):
    pass


class PrometheusQueryError(PrometheusError):
    pass


class PrometheusProviderAdapter(Protocol):
    def get_pod_runtime(self, namespace: str, pod_name: str) -> dict[str, object]: ...
    def get_pod_cpu_usage(self, namespace: str, pod_name: str) -> dict[str, object]: ...
    def get_deployment_restart_rate(
        self, namespace: str, deployment_name: str
    ) -> dict[str, object]: ...


class FakePrometheusProviderAdapter:
    def get_pod_runtime(self, namespace: str, pod_name: str) -> dict[str, object]:
        return {
            "namespace": namespace,
            "pod_name": pod_name,
            "ready": True,
            "restart_count": 0,
            "recent_restart_increase": 0.0,
            "window": "15m",
        }

    def get_pod_cpu_usage(self, namespace: str, pod_name: str) -> dict[str, object]:
        return {
            "namespace": namespace,
            "pod_name": pod_name,
            "avg_cpu_cores_5m": 0.03,
            "window": "5m",
        }

    def get_deployment_restart_rate(
        self, namespace: str, deployment_name: str
    ) -> dict[str, object]:
        return {
            "namespace": namespace,
            "deployment_name": deployment_name,
            "recent_restarts_15m": 3,
            "total_restarts": 7,
            "pod_breakdown": [
                {
                    "pod_name": f"{deployment_name}-abc",
                    "recent_restarts_15m": 2,
                    "total_restarts": 4,
                },
                {
                    "pod_name": f"{deployment_name}-def",
                    "recent_restarts_15m": 1,
                    "total_restarts": 3,
                },
            ],
            "pods_shown": 2,
            "pods_total": 2,
            "no_pods": False,
            "window": "15m",
        }


class RealPrometheusProviderAdapter:
    _PROMQL_REGEX_META_CHARS = frozenset(".+*?^$()[]{}|\\")

    def __init__(self, base_url: str, timeout_seconds: int = 10) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def query_instant(self, query: str, query_name: str = "instant_query") -> dict[str, Any]:
        encoded = urlencode({"query": query})
        url = f"{self._base_url}/api/v1/query?{encoded}"
        try:
            with urlopen(url, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as error:
            status = error.code if isinstance(error, HTTPError) else "n/a"
            logger.warning(
                "prometheus query failed query_name=%s http_status=%s error_type=%s query_length=%s",
                query_name,
                status,
                type(error).__name__,
                len(query),
                exc_info=True,
            )
            raise PrometheusQueryError("failed to query prometheus") from error

        if payload.get("status") != "success":
            logger.warning(
                "prometheus query returned non-success status query_name=%s query_length=%s payload_status=%s",
                query_name,
                len(query),
                payload.get("status"),
            )
            raise PrometheusQueryError("prometheus query returned non-success status")

        data = payload.get("data", {})
        result = data.get("result", [])
        if not isinstance(result, list):
            raise PrometheusQueryError("prometheus result must be a list")
        return {"result": result}

    def _result_series_names(self, result: list[dict[str, Any]], label: str) -> list[str]:
        names: list[str] = []
        for sample in result:
            metric = sample.get("metric", {})
            value = metric.get(label)
            if isinstance(value, str):
                names.append(value)
        return names

    def _escape_promql_regex_literal(self, value: str) -> str:
        escaped: list[str] = []
        for char in value:
            if char == '"':
                escaped.append('\\"')
                continue
            if char in self._PROMQL_REGEX_META_CHARS:
                escaped.append("\\\\")
            escaped.append(char)
        return "".join(escaped)

    def _regex_union(self, values: list[str]) -> str:
        return "|".join(self._escape_promql_regex_literal(value) for value in values)

    def get_pod_runtime(self, namespace: str, pod_name: str) -> dict[str, object]:
        ready_result = self.query_instant(
            f'kube_pod_status_ready{{namespace="{namespace}",pod="{pod_name}",condition="true"}}',
            query_name="pod_runtime_ready",
        )["result"]
        restart_result = self.query_instant(
            f'kube_pod_container_status_restarts_total{{namespace="{namespace}",pod="{pod_name}"}}',
            query_name="pod_runtime_restart_total",
        )["result"]
        increase_result = self.query_instant(
            'sum(increase(kube_pod_container_status_restarts_total'
            f'{{namespace="{namespace}",pod="{pod_name}"}}[15m]))',
            query_name="pod_runtime_restart_increase_15m",
        )["result"]

        if not ready_result and not restart_result:
            raise PrometheusQueryError("no metrics found for pod")

        ready = bool(ready_result) and float(ready_result[0]["value"][1]) == 1.0
        restart_count = sum(float(sample["value"][1]) for sample in restart_result)
        recent_restart_increase = (
            float(increase_result[0]["value"][1]) if increase_result else 0.0
        )

        return {
            "namespace": namespace,
            "pod_name": pod_name,
            "ready": ready,
            "restart_count": int(restart_count),
            "recent_restart_increase": recent_restart_increase,
            "window": "15m",
        }

    def get_pod_cpu_usage(self, namespace: str, pod_name: str) -> dict[str, object]:
        cpu_result = self.query_instant(
            'sum(rate(container_cpu_usage_seconds_total'
            f'{{namespace="{namespace}",pod="{pod_name}",container!="",image!=""}}[5m]))',
            query_name="pod_cpu_usage_5m",
        )["result"]

        if not cpu_result:
            raise PrometheusQueryError("no cpu metrics found for pod")

        avg_cpu_cores_5m = float(cpu_result[0]["value"][1])

        return {
            "namespace": namespace,
            "pod_name": pod_name,
            "avg_cpu_cores_5m": avg_cpu_cores_5m,
            "window": "5m",
        }

    def get_deployment_restart_rate(
        self, namespace: str, deployment_name: str
    ) -> dict[str, object]:
        rs_result = self.query_instant(
            f'kube_replicaset_owner{{owner_kind="Deployment",owner_name="{deployment_name}",namespace="{namespace}"}}',
            query_name="deployment_replicaset_lookup",
        )["result"]
        if not rs_result:
            raise PrometheusQueryError("no replicasets found for deployment")

        replicasets = self._result_series_names(rs_result, "replicaset")
        rs_regex = self._regex_union(replicasets)

        pod_result = self.query_instant(
            f'kube_pod_owner{{owner_kind="ReplicaSet",owner_name=~"{rs_regex}",namespace="{namespace}"}}',
            query_name="deployment_pod_lookup",
        )["result"]
        if not pod_result:
            return {
                "namespace": namespace,
                "deployment_name": deployment_name,
                "recent_restarts_15m": 0,
                "total_restarts": 0,
                "pod_breakdown": [],
                "pods_shown": 0,
                "pods_total": 0,
                "no_pods": True,
                "window": "15m",
            }

        pods = self._result_series_names(pod_result, "pod")
        pod_regex = self._regex_union(pods)

        total_result = self.query_instant(
            'sum by(pod)(kube_pod_container_status_restarts_total'
            f'{{pod=~"{pod_regex}",namespace="{namespace}"}})',
            query_name="deployment_restart_total",
        )["result"]
        recent_result = self.query_instant(
            'sum by(pod)(increase(kube_pod_container_status_restarts_total'
            f'{{pod=~"{pod_regex}",namespace="{namespace}"}}[15m]))',
            query_name="deployment_restart_increase_15m",
        )["result"]

        total_by_pod = {
            sample["metric"]["pod"]: int(float(sample["value"][1]))
            for sample in total_result
        }
        recent_by_pod = {
            sample["metric"]["pod"]: int(float(sample["value"][1]))
            for sample in recent_result
        }

        if not total_by_pod and not recent_by_pod:
            return {
                "namespace": namespace,
                "deployment_name": deployment_name,
                "recent_restarts_15m": 0,
                "total_restarts": 0,
                "pod_breakdown": [],
                "pods_shown": 0,
                "pods_total": len(pods),
                "no_pods": False,
                "window": "15m",
            }

        pod_breakdown = [
            {
                "pod_name": pod,
                "recent_restarts_15m": recent_by_pod.get(pod, 0),
                "total_restarts": total_by_pod.get(pod, 0),
            }
            for pod in pods
        ]
        pod_breakdown.sort(
            key=lambda item: (
                item["recent_restarts_15m"],
                item["total_restarts"],
            ),
            reverse=True,
        )
        pods_total = len(pod_breakdown)
        pod_breakdown = pod_breakdown[:5]

        return {
            "namespace": namespace,
            "deployment_name": deployment_name,
            "recent_restarts_15m": sum(recent_by_pod.values()),
            "total_restarts": sum(total_by_pod.values()),
            "pod_breakdown": pod_breakdown,
            "pods_shown": len(pod_breakdown),
            "pods_total": pods_total,
            "no_pods": False,
            "window": "15m",
        }
