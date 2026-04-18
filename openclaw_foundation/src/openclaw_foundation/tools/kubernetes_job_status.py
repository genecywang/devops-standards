from openclaw_foundation.adapters.kubernetes import KubernetesProviderAdapter
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult
from openclaw_foundation.runtime.guards import (
    redact_output,
    truncate_job_status,
    validate_scope,
)
from openclaw_foundation.tools.investigation_metadata import make_investigation_metadata


class KubernetesJobStatusTool:
    tool_name = "get_job_status"
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
            raise ValueError("target is required for get_job_status")

        cluster = request.target["cluster"]
        namespace = request.target["namespace"]
        job_name = request.target.get("resource_name") or request.target.get("job_name")
        if job_name is None:
            raise ValueError("resource_name or job_name is required for get_job_status")

        validate_scope(cluster, namespace, self._allowed_clusters, self._allowed_namespaces)

        payload = self._adapter.get_job_status(cluster, namespace, job_name)
        truncated = truncate_job_status(payload)
        redacted = redact_output(truncated)

        active = int(redacted.get("active", 0) or 0)
        succeeded = int(redacted.get("succeeded", 0) or 0)
        failed = int(redacted.get("failed", 0) or 0)
        owner_kind = redacted.get("owner_kind")
        owner_name = redacted.get("owner_name")
        owner_suffix = ""
        if isinstance(owner_kind, str) and isinstance(owner_name, str) and owner_kind and owner_name:
            owner_suffix = f", owned by {owner_kind.lower()} {owner_name}"

        summary = _build_job_summary(
            job_name=job_name,
            payload=redacted,
        )

        return ToolResult(
            summary=f"{summary}{owner_suffix}",
            evidence=[redacted],
            metadata=_build_job_metadata(redacted),
        )


def _build_job_summary(job_name: str, payload: dict[str, object]) -> str:
    active = int(payload.get("active", 0) or 0)
    succeeded = int(payload.get("succeeded", 0) or 0)
    failed = int(payload.get("failed", 0) or 0)
    detail_suffix = _build_job_summary_detail(payload)
    completion_time = payload.get("completion_time")

    if failed:
        return f"job {job_name} failed: active={active}, succeeded={succeeded}, failed={failed}{detail_suffix}"

    if active:
        return f"job {job_name} is still running: active={active}"

    if succeeded:
        completion_suffix = ""
        if isinstance(completion_time, str) and completion_time:
            completion_suffix = f", completion_time={completion_time}"
        return (
            f"job {job_name} completed successfully: succeeded={succeeded}, failed={failed}"
            f"{completion_suffix}{detail_suffix}"
        )

    return f"job {job_name} has not completed yet: active={active}, succeeded={succeeded}, failed={failed}{detail_suffix}"


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


def _build_job_metadata(payload: dict[str, object]) -> dict[str, object]:
    active = int(payload.get("active", 0) or 0)
    succeeded = int(payload.get("succeeded", 0) or 0)
    failed = int(payload.get("failed", 0) or 0)
    primary_reason = _primary_job_reason(payload)

    if failed:
        return make_investigation_metadata(
            health_state="failed",
            attention_required=True,
            resource_exists=True,
            primary_reason=primary_reason,
        )

    if active:
        return make_investigation_metadata(
            health_state="in_progress",
            attention_required=False,
            resource_exists=True,
            primary_reason=primary_reason or "Running",
        )

    if succeeded:
        return make_investigation_metadata(
            health_state="healthy",
            attention_required=False,
            resource_exists=True,
            primary_reason=primary_reason,
        )

    return make_investigation_metadata(
        health_state="pending",
        attention_required=False,
        resource_exists=True,
        primary_reason=primary_reason or "Pending",
    )


def _primary_job_reason(payload: dict[str, object]) -> str:
    conditions = payload.get("conditions", [])
    if isinstance(conditions, list):
        for condition in conditions:
            if not isinstance(condition, dict):
                continue
            if str(condition.get("status") or "").lower() != "true":
                continue
            reason = str(condition.get("reason") or "").strip()
            if reason:
                return reason

    active = int(payload.get("active", 0) or 0)
    succeeded = int(payload.get("succeeded", 0) or 0)
    failed = int(payload.get("failed", 0) or 0)
    if failed:
        return "Failed"
    if active:
        return "Running"
    if succeeded:
        return "Completed"
    return "Pending"
