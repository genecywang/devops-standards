from openclaw_foundation.adapters.aws import AwsProviderAdapter, AwsResourceNotFoundError
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult
from openclaw_foundation.runtime.guards import redact_output, truncate_load_balancer_status
from openclaw_foundation.tools.investigation_metadata import (
    HEALTH_STATE_DEGRADED,
    HEALTH_STATE_FAILED,
    HEALTH_STATE_GONE,
    HEALTH_STATE_HEALTHY,
    make_investigation_metadata,
)


class AwsLoadBalancerStatusTool:
    tool_name = "get_load_balancer_status"
    supported_request_types = ("investigation",)

    def __init__(self, adapter: AwsProviderAdapter) -> None:
        self._adapter = adapter

    def invoke(self, request: InvestigationRequest) -> ToolResult:
        if request.target is None:
            raise ValueError("target is required for get_load_balancer_status")

        region_code = str(request.scope.get("region_code") or "").strip()
        if not region_code:
            raise ValueError("scope.region_code is required for get_load_balancer_status")

        load_balancer_name = request.target.get("resource_name") or request.target.get("load_balancer_name")
        if load_balancer_name is None:
            raise ValueError("resource_name or load_balancer_name is required for get_load_balancer_status")

        try:
            payload = self._adapter.get_load_balancer_status(region_code, load_balancer_name)
        except AwsResourceNotFoundError:
            return ToolResult(
                summary=f"load balancer {load_balancer_name} does not exist in region {region_code}",
                evidence=[],
                metadata=make_investigation_metadata(
                    health_state=HEALTH_STATE_GONE,
                    attention_required=False,
                    resource_exists=False,
                    primary_reason="NotFound",
                ),
            )

        truncated = truncate_load_balancer_status(payload)
        redacted = redact_output(truncated)
        state = str(redacted.get("state") or "unknown")

        return ToolResult(
            summary=(
                f"load balancer {load_balancer_name} is {state}: "
                f"type={redacted.get('type')}, "
                f"scheme={redacted.get('scheme')}, "
                f"state={state}, "
                f"vpc_id={redacted.get('vpc_id')}, "
                f"availability_zones={redacted.get('availability_zone_count')}, "
                f"security_groups={redacted.get('security_group_count')}"
            ),
            evidence=[redacted],
            metadata=_build_load_balancer_metadata(state),
        )


def _build_load_balancer_metadata(state: str) -> dict[str, object]:
    normalized = state.lower()
    if normalized == "active":
        return make_investigation_metadata(
            health_state=HEALTH_STATE_HEALTHY,
            attention_required=False,
            resource_exists=True,
            primary_reason=state,
        )
    if normalized in {"provisioning", "active_impaired"}:
        return make_investigation_metadata(
            health_state=HEALTH_STATE_DEGRADED,
            attention_required=True,
            resource_exists=True,
            primary_reason=state,
        )
    return make_investigation_metadata(
        health_state=HEALTH_STATE_FAILED,
        attention_required=True,
        resource_exists=True,
        primary_reason=state or "unknown",
    )
