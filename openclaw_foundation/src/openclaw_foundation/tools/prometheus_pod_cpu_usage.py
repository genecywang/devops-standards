from openclaw_foundation.adapters.prometheus import PrometheusProviderAdapter
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult


class PrometheusPodCpuUsageTool:
    tool_name = "get_pod_cpu_usage"
    supported_request_types = ("investigation",)

    def __init__(
        self,
        adapter: PrometheusProviderAdapter,
        allowed_namespaces: set[str],
    ) -> None:
        self._adapter = adapter
        self._allowed_namespaces = allowed_namespaces

    def invoke(self, request: InvestigationRequest) -> ToolResult:
        if request.target is None:
            raise ValueError("target is required for get_pod_cpu_usage")

        namespace = request.target["namespace"]
        pod_name = request.target.get("resource_name") or request.target.get("pod_name")
        if pod_name is None:
            raise ValueError("resource_name or pod_name is required for get_pod_cpu_usage")
        if namespace not in self._allowed_namespaces:
            raise PermissionError("namespace is not allowed")

        payload = self._adapter.get_pod_cpu_usage(namespace, pod_name)
        avg_cpu_cores_5m = payload["avg_cpu_cores_5m"]
        state = "quiet"
        if avg_cpu_cores_5m >= 0.5:
            state = "hot"
        elif avg_cpu_cores_5m >= 0.1:
            state = "active"

        return ToolResult(
            summary=(
                f"pod {pod_name} cpu usage looks {state}: "
                f"{avg_cpu_cores_5m:.2f} cores avg over {payload['window']}"
            ),
            evidence=[payload],
        )
