from openclaw_foundation.adapters.prometheus import PrometheusProviderAdapter
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult


class PrometheusPodRuntimeTool:
    tool_name = "get_pod_runtime"
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
            raise ValueError("target is required for get_pod_runtime")

        namespace = request.target["namespace"]
        pod_name = request.target.get("resource_name") or request.target.get("pod_name")
        if pod_name is None:
            raise ValueError("resource_name or pod_name is required for get_pod_runtime")
        if namespace not in self._allowed_namespaces:
            raise PermissionError("namespace is not allowed")

        payload = self._adapter.get_pod_runtime(namespace, pod_name)
        ready = payload["ready"]
        recent_restart_increase = payload["recent_restart_increase"]
        state = "stable" if ready and recent_restart_increase == 0 else "unstable"
        readiness = "ready" if ready else "not ready"

        return ToolResult(
            summary=(
                f"pod {pod_name} runtime looks {state}: "
                f"{readiness}, {recent_restart_increase:g} restarts in {payload['window']}"
            ),
            evidence=[payload],
        )
