from __future__ import annotations

import json
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


class PrometheusError(RuntimeError):
    pass


class PrometheusQueryError(PrometheusError):
    pass


class PrometheusProviderAdapter(Protocol):
    def get_pod_runtime(self, namespace: str, pod_name: str) -> dict[str, object]: ...


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


class RealPrometheusProviderAdapter:
    def __init__(self, base_url: str, timeout_seconds: int = 10) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def query_instant(self, query: str) -> dict[str, Any]:
        encoded = urlencode({"query": query})
        url = f"{self._base_url}/api/v1/query?{encoded}"
        try:
            with urlopen(url, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as error:
            raise PrometheusQueryError("failed to query prometheus") from error

        if payload.get("status") != "success":
            raise PrometheusQueryError("prometheus query returned non-success status")

        data = payload.get("data", {})
        result = data.get("result", [])
        if not isinstance(result, list):
            raise PrometheusQueryError("prometheus result must be a list")
        return {"result": result}

    def get_pod_runtime(self, namespace: str, pod_name: str) -> dict[str, object]:
        ready_result = self.query_instant(
            f'kube_pod_status_ready{{namespace="{namespace}",pod="{pod_name}",condition="true"}}'
        )["result"]
        restart_result = self.query_instant(
            f'kube_pod_container_status_restarts_total{{namespace="{namespace}",pod="{pod_name}"}}'
        )["result"]
        increase_result = self.query_instant(
            'sum(increase(kube_pod_container_status_restarts_total'
            f'{{namespace="{namespace}",pod="{pod_name}"}}[15m]))'
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
