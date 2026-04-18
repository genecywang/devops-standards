from openclaw_foundation.adapters.kubernetes import KubernetesProviderAdapter
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult
from openclaw_foundation.runtime.guards import (
    redact_output,
    truncate_job_status,
    validate_scope,
)
from openclaw_foundation.tools.investigation_metadata import (
    HEALTH_STATE_IDLE,
    HEALTH_STATE_SUSPENDED,
    make_investigation_metadata,
)
from openclaw_foundation.tools.kubernetes_job_status import _build_job_summary
from openclaw_foundation.tools.kubernetes_job_status import _build_job_metadata


class KubernetesCronJobStatusTool:
    tool_name = "get_cronjob_status"
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
            raise ValueError("target is required for get_cronjob_status")

        cluster = request.target["cluster"]
        namespace = request.target["namespace"]
        cronjob_name = request.target.get("resource_name") or request.target.get("cronjob_name")
        if cronjob_name is None:
            raise ValueError("resource_name or cronjob_name is required for get_cronjob_status")

        validate_scope(cluster, namespace, self._allowed_clusters, self._allowed_namespaces)

        payload = self._adapter.get_cronjob_status(cluster, namespace, cronjob_name)
        truncated = truncate_job_status(payload)
        redacted = redact_output(truncated)
        cronjob_prefix = _build_cronjob_prefix(cronjob_name, redacted)
        suspended = bool(redacted.get("suspend", False))

        latest_job_name = redacted.get("latest_job_name")
        if not isinstance(latest_job_name, str) or not latest_job_name:
            if suspended:
                summary = f"{cronjob_prefix} is suspended; no recent jobs"
            else:
                summary = f"{cronjob_prefix} has no recent jobs"
            return ToolResult(
                summary=summary,
                evidence=[redacted],
                metadata=_build_cronjob_idle_metadata(suspended),
            )

        job_summary = _build_job_summary(latest_job_name, redacted)
        return ToolResult(
            summary=f"{cronjob_prefix}; latest {job_summary}",
            evidence=[redacted],
            metadata=_build_job_metadata(redacted),
        )


def _build_cronjob_prefix(cronjob_name: str, payload: dict[str, object]) -> str:
    parts = [f"cronjob {cronjob_name}"]

    schedule = payload.get("schedule")
    if isinstance(schedule, str) and schedule:
        parts.append(f'schedule="{schedule}"')

    suspend = payload.get("suspend")
    if isinstance(suspend, bool):
        parts.append(f"suspend={'true' if suspend else 'false'}")

    last_schedule = payload.get("last_schedule_time")
    if isinstance(last_schedule, str) and last_schedule:
        parts.append(f"last_schedule={last_schedule}")

    return " ".join(parts)


def _build_cronjob_idle_metadata(suspended: bool) -> dict[str, object]:
    if suspended:
        return make_investigation_metadata(
            health_state=HEALTH_STATE_SUSPENDED,
            attention_required=False,
            resource_exists=True,
            primary_reason="Suspended",
        )

    return make_investigation_metadata(
        health_state=HEALTH_STATE_IDLE,
        attention_required=False,
        resource_exists=True,
        primary_reason="NoRecentJobs",
    )
