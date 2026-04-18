from openclaw_foundation.adapters.kubernetes import (
    KubernetesProviderAdapter,
    KubernetesResourceNotFoundError,
)
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult
from openclaw_foundation.runtime.guards import (
    redact_output,
    truncate_pod_events,
    truncate_pod_status,
    validate_scope,
)
from openclaw_foundation.tools.investigation_metadata import make_investigation_metadata


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

        pod_status_summary: str | None = None
        try:
            pod_status = self._adapter.get_pod_status(cluster, namespace, pod_name)
        except KubernetesResourceNotFoundError:
            pod_status = None
            pod_status_summary = f"pod {pod_name} no longer exists"
        else:
            truncated_status = truncate_pod_status(pod_status)
            redacted_status = redact_output(truncated_status)
            pod_status_summary = _summarize_pod_status(pod_name, redacted_status)
        events = self._adapter.get_pod_events(cluster, namespace, pod_name)
        truncated = truncate_pod_events(events)
        redacted = [redact_output(event) for event in truncated]
        return ToolResult(
            summary=_summarize_pod_events(pod_name, pod_status_summary, redacted),
            evidence=redacted,
            metadata=_build_pod_metadata(redacted_status if pod_status is not None else None),
        )


def _summarize_pod_events(
    pod_name: str,
    pod_status_summary: str | None,
    events: list[dict[str, object]],
) -> str:
    status_summary = pod_status_summary or f"pod {pod_name} status unavailable"
    if not events:
        return f"{status_summary}; no recent events"

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
            f"{status_summary}; Warning events: {top_reasons}; "
            f"latest reason={latest_reason}; message={latest_message}"
        )

    if _status_is_healthy_without_recent_warnings(status_summary):
        return f"{status_summary}; no recent Warning events"

    latest_event = events[0]
    latest_type = str(latest_event.get("type") or "Unknown")
    latest_reason = str(latest_event.get("reason") or "Unknown")
    latest_message = str(latest_event.get("message") or "-")
    return (
        f"{status_summary}; "
        f"latest event={latest_type}/{latest_reason}; message={latest_message}"
    )


def _summarize_pod_status(pod_name: str, pod_status: dict[str, object]) -> str:
    phase = str(pod_status.get("phase") or "Unknown")
    container_summaries: list[str] = []
    needs_attention = phase not in {"Running", "Succeeded"}

    for container in pod_status.get("container_statuses", []):
        if not isinstance(container, dict):
            continue

        name = str(container.get("name") or "unknown")
        state = container.get("state", {})
        restart_count = container.get("restart_count")

        if isinstance(state, dict) and state.get("waiting_reason"):
            needs_attention = True
            container_summaries.append(f"container {name} waiting reason={state['waiting_reason']}")
        elif isinstance(state, dict) and state.get("terminated_reason"):
            needs_attention = True
            summary = f"container {name} last terminated reason={state['terminated_reason']}"
            if state.get("terminated_exit_code") is not None:
                summary += f" exit_code={state['terminated_exit_code']}"
            if restart_count:
                summary += f" restart_count={restart_count}"
            container_summaries.append(summary)
        elif restart_count:
            needs_attention = True
            container_summaries.append(f"container {name} restart_count={restart_count}")

    summary_phase = f"pod {pod_name} is {phase}"
    if needs_attention and phase == "Running":
        summary_phase = f"pod {pod_name} is Running but needs attention"
    elif needs_attention:
        summary_phase = f"pod {pod_name} is {phase} and needs attention"

    parts = [summary_phase]
    if container_summaries:
        parts.append("; ".join(container_summaries[:2]))

    return "; ".join(parts)


def _status_is_healthy_without_recent_warnings(status_summary: str) -> bool:
    return (
        status_summary.startswith("pod ")
        and " is Running" in status_summary
        and "needs attention" not in status_summary
        and "waiting reason=" not in status_summary
        and "last terminated reason=" not in status_summary
        and "restart_count=" not in status_summary
    )


def _build_pod_metadata(pod_status: dict[str, object] | None) -> dict[str, object]:
    if pod_status is None:
        return make_investigation_metadata(
            health_state="gone",
            attention_required=False,
            resource_exists=False,
            primary_reason="Deleted",
        )

    phase = str(pod_status.get("phase") or "Unknown")
    container_statuses = pod_status.get("container_statuses", [])
    primary_reason = phase
    attention_required = phase not in {"Running", "Succeeded"}
    health_state = "healthy" if phase in {"Running", "Succeeded"} else "degraded"

    if isinstance(container_statuses, list):
        for container in container_statuses:
            if not isinstance(container, dict):
                continue
            state = container.get("state", {})
            if isinstance(state, dict) and state.get("waiting_reason"):
                primary_reason = str(state["waiting_reason"])
                attention_required = True
                health_state = "degraded"
                break
            if isinstance(state, dict) and state.get("terminated_reason"):
                primary_reason = str(state["terminated_reason"])
                attention_required = True
                health_state = "degraded"
                break
            restart_count = int(container.get("restart_count", 0) or 0)
            if restart_count > 0:
                primary_reason = "Restarting"
                attention_required = True
                health_state = "degraded"
                break

    return make_investigation_metadata(
        health_state=health_state,
        attention_required=attention_required,
        resource_exists=True,
        primary_reason=primary_reason,
    )
