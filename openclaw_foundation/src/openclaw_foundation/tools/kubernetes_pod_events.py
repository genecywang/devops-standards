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
        pod_name = request.target.get("resource_name") or request.target.get("pod_name")
        if pod_name is None:
            raise ValueError("resource_name or pod_name is required for get_pod_events")
        validate_scope(cluster, namespace, self._allowed_clusters, self._allowed_namespaces)

        events = self._adapter.get_pod_events(cluster, namespace, pod_name)
        truncated = truncate_pod_events(events)
        redacted = [redact_output(event) for event in truncated]
        return ToolResult(
            summary=_summarize_pod_events(pod_name, redacted),
            evidence=redacted,
        )


def _summarize_pod_events(pod_name: str, events: list[dict[str, object]]) -> str:
    if not events:
        return f"pod {pod_name} has no recent events"

    warning_events = [event for event in events if event.get("type") == "Warning"]
    if warning_events:
        reason_counts: dict[str, int] = {}
        for event in warning_events:
            reason = str(event.get("reason") or "Unknown")
            count = event.get("count", 1)
            reason_counts[reason] = reason_counts.get(reason, 0) + (count if isinstance(count, int) else 1)

        ordered_reasons = sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
        top_reasons = ", ".join(f"{reason} x{count}" for reason, count in ordered_reasons[:3])
        latest_warning = warning_events[0]
        latest_reason = str(latest_warning.get("reason") or "Unknown")
        latest_message = str(latest_warning.get("message") or "-")
        return (
            f"pod {pod_name} has recent Warning events: {top_reasons}; "
            f"latest reason={latest_reason}; message={latest_message}"
        )

    latest_event = events[0]
    latest_type = str(latest_event.get("type") or "Unknown")
    latest_reason = str(latest_event.get("reason") or "Unknown")
    latest_message = str(latest_event.get("message") or "-")
    return (
        f"pod {pod_name} has {len(events)} recent events; "
        f"latest event={latest_type}/{latest_reason}; message={latest_message}"
    )
