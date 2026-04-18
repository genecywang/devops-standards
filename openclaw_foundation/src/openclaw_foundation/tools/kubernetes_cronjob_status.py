from openclaw_foundation.adapters.kubernetes import KubernetesProviderAdapter
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult
from openclaw_foundation.runtime.guards import (
    redact_output,
    truncate_job_status,
    validate_scope,
)


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

        latest_job_name = redacted.get("latest_job_name")
        if not isinstance(latest_job_name, str) or not latest_job_name:
            return ToolResult(
                summary=f"{cronjob_prefix} has no recent jobs",
                evidence=[redacted],
            )

        active = redacted.get("active", 0)
        succeeded = redacted.get("succeeded", 0)
        failed = redacted.get("failed", 0)
        if failed:
            health = "failed"
        elif active:
            health = "running"
        elif succeeded:
            health = "succeeded"
        else:
            health = "pending"

        detail_suffix = _build_job_summary_detail(redacted)
        return ToolResult(
            summary=(
                f"{cronjob_prefix}; latest job {latest_job_name} is {health}: "
                f"active={active}, succeeded={succeeded}, failed={failed}{detail_suffix}"
            ),
            evidence=[redacted],
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


def _build_job_summary_detail(payload: dict[str, object]) -> str:
    conditions = payload.get("conditions", [])
    if not isinstance(conditions, list):
        return ""

    for condition in conditions:
        if not isinstance(condition, dict):
            continue
        if str(condition.get("status") or "").lower() != "true":
            continue

        reason = str(condition.get("reason") or "").strip()
        message = str(condition.get("message") or "").strip()
        if not reason and not message:
            continue

        parts = []
        if reason:
            parts.append(f"reason={reason}")
        if message:
            parts.append(f"message={message}")
        return ", " + ", ".join(parts)

    return ""
