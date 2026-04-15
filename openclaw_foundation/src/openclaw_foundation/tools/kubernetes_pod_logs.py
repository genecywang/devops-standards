from openclaw_foundation.adapters.kubernetes import KubernetesProviderAdapter
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult
from openclaw_foundation.runtime.guards import redact_log_lines, truncate_pod_logs, validate_scope


class KubernetesPodLogsTool:
    tool_name = "get_pod_logs"
    supported_request_types = ("investigation",)

    def __init__(
        self,
        adapter: KubernetesProviderAdapter,
        allowed_clusters: set[str],
        allowed_namespaces: set[str],
    ) -> None:
        self._adapter = adapter
        self._allowed_clusters = allowed_clusters
        self._allowed_namespaces = allowed_namespaces

    def invoke(self, request: InvestigationRequest) -> ToolResult:
        if request.target is None:
            raise ValueError("target is required for get_pod_logs")

        cluster = request.target["cluster"]
        namespace = request.target["namespace"]
        pod_name = request.target.get("resource_name") or request.target.get("pod_name")
        if pod_name is None:
            raise ValueError("resource_name or pod_name is required for get_pod_logs")
        validate_scope(cluster, namespace, self._allowed_clusters, self._allowed_namespaces)

        lines = self._adapter.get_pod_logs(cluster, namespace, pod_name)
        truncated = truncate_pod_logs(lines)
        redacted = redact_log_lines(truncated)

        if not redacted:
            summary = f"pod {pod_name} has no recent logs"
        else:
            summary = f"pod {pod_name} last {len(redacted)} log lines\n" + "\n".join(redacted)

        return ToolResult(
            summary=summary,
            evidence=[{"line": line} for line in redacted],
        )
