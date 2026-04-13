from openclaw_foundation.adapters.kubernetes import KubernetesProviderAdapter
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult
from openclaw_foundation.runtime.guards import redact_output, truncate_pod_events, validate_scope


class KubernetesPodEventsTool:
    tool_name = "get_pod_events"
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
            raise ValueError("target is required for get_pod_events")

        cluster = request.target["cluster"]
        namespace = request.target["namespace"]
        pod_name = request.target["pod_name"]
        validate_scope(cluster, namespace, self._allowed_clusters, self._allowed_namespaces)

        events = self._adapter.get_pod_events(cluster, namespace, pod_name)
        truncated = truncate_pod_events(events)
        redacted = [redact_output(event) for event in truncated]
        return ToolResult(
            summary=f"pod {pod_name} has {len(redacted)} recent events",
            evidence=redacted,
        )
