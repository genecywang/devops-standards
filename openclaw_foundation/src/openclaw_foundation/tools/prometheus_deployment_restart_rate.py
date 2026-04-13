from openclaw_foundation.adapters.prometheus import PrometheusProviderAdapter
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult


class PrometheusDeploymentRestartRateTool:
    tool_name = "get_deployment_restart_rate"
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
            raise ValueError("target is required for get_deployment_restart_rate")

        namespace = request.target["namespace"]
        deployment_name = request.target.get("resource_name")
        if deployment_name is None:
            raise ValueError("resource_name is required for get_deployment_restart_rate")
        if namespace not in self._allowed_namespaces:
            raise PermissionError("namespace is not allowed")

        payload = self._adapter.get_deployment_restart_rate(namespace, deployment_name)
        state = "quiet" if payload["recent_restarts_15m"] == 0 else "elevated"
        summary = (
            f"deployment {deployment_name} restart activity is {state}: "
            f"{payload['recent_restarts_15m']} restarts in {payload['window']}, "
            f"{payload['total_restarts']} total"
        )

        pod_breakdown = payload["pod_breakdown"]
        if pod_breakdown:
            top_pods = ", ".join(
                f"{item['pod_name']} ({item['recent_restarts_15m']} recent, {item['total_restarts']} total)"
                for item in pod_breakdown
            )
            if payload["pods_shown"] < payload["pods_total"]:
                summary += (
                    f" top pods: {top_pods}, ... "
                    f"(showing {payload['pods_shown']} of {payload['pods_total']})"
                )
            else:
                summary += f" top pods: {top_pods}"
        elif payload["no_pods"]:
            summary += " no pods found for deployment"
        else:
            summary += " no pod restart metrics found"

        return ToolResult(summary=summary, evidence=[payload])
