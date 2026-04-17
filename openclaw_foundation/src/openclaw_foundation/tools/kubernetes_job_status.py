from openclaw_foundation.adapters.kubernetes import KubernetesProviderAdapter
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult
from openclaw_foundation.runtime.guards import (
    redact_output,
    truncate_job_status,
    validate_scope,
)


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

        active = redacted.get("active", 0)
        succeeded = redacted.get("succeeded", 0)
        failed = redacted.get("failed", 0)
        owner_kind = redacted.get("owner_kind")
        owner_name = redacted.get("owner_name")
        if failed:
            health = "failed"
        elif active:
            health = "running"
        elif succeeded:
            health = "succeeded"
        else:
            health = "pending"

        owner_suffix = ""
        if isinstance(owner_kind, str) and isinstance(owner_name, str) and owner_kind and owner_name:
            owner_suffix = f", owned by {owner_kind.lower()} {owner_name}"

        return ToolResult(
            summary=(
                f"job {job_name} is {health}: active={active}, succeeded={succeeded}, failed={failed}"
                f"{owner_suffix}"
            ),
            evidence=[redacted],
        )
