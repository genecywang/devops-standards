from openclaw_foundation.adapters.kubernetes import KubernetesProviderAdapter
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult
from openclaw_foundation.runtime.guards import (
    redact_output,
    truncate_deployment_status,
    validate_scope,
)
from openclaw_foundation.tools.investigation_metadata import (
    HEALTH_STATE_DEGRADED,
    HEALTH_STATE_HEALTHY,
    make_investigation_metadata,
)


class KubernetesDeploymentStatusTool:
    tool_name = "get_deployment_status"
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
            raise ValueError("target is required for get_deployment_status")

        cluster = request.target["cluster"]
        namespace = request.target["namespace"]
        deployment_name = request.target.get("resource_name") or request.target.get("deployment_name")
        if deployment_name is None:
            raise ValueError("resource_name or deployment_name is required for get_deployment_status")

        validate_scope(cluster, namespace, self._allowed_clusters, self._allowed_namespaces)

        payload = self._adapter.get_deployment_status(cluster, namespace, deployment_name)
        truncated = truncate_deployment_status(payload)
        redacted = redact_output(truncated)

        desired = redacted.get("desired_replicas", 0)
        ready = redacted.get("ready_replicas", 0)
        available = redacted.get("available_replicas", 0)
        health = HEALTH_STATE_HEALTHY if desired == ready == available else HEALTH_STATE_DEGRADED
        primary_reason = "ReplicasMismatch"
        for condition in redacted.get("conditions", []):
            if condition.get("status") == "True" and condition.get("reason"):
                primary_reason = str(condition["reason"])
                break

        return ToolResult(
            summary=f"deployment {deployment_name} is {health}: {ready}/{desired} ready, {available} available",
            evidence=[redacted],
            metadata=make_investigation_metadata(
                health_state=health,
                attention_required=health != HEALTH_STATE_HEALTHY,
                resource_exists=True,
                primary_reason=primary_reason,
            ),
        )
