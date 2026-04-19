from openclaw_foundation.adapters.aws import AwsProviderAdapter, AwsResourceNotFoundError
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult
from openclaw_foundation.runtime.guards import redact_output, truncate_target_group_status
from openclaw_foundation.tools.investigation_metadata import (
    HEALTH_STATE_DEGRADED,
    HEALTH_STATE_FAILED,
    HEALTH_STATE_GONE,
    HEALTH_STATE_HEALTHY,
    make_investigation_metadata,
)


class AwsTargetGroupStatusTool:
    tool_name = "get_target_group_status"
    supported_request_types = ("investigation",)

    def __init__(self, adapter: AwsProviderAdapter) -> None:
        self._adapter = adapter

    def invoke(self, request: InvestigationRequest) -> ToolResult:
        if request.target is None:
            raise ValueError("target is required for get_target_group_status")

        region_code = str(request.scope.get("region_code") or "").strip()
        if not region_code:
            raise ValueError("scope.region_code is required for get_target_group_status")

        target_group_name = request.target.get("resource_name") or request.target.get("target_group_name")
        if target_group_name is None:
            raise ValueError("resource_name or target_group_name is required for get_target_group_status")

        try:
            payload = self._adapter.get_target_group_status(region_code, target_group_name)
        except AwsResourceNotFoundError:
            return ToolResult(
                summary=f"target group {target_group_name} does not exist in region {region_code}",
                evidence=[],
                metadata=make_investigation_metadata(
                    health_state=HEALTH_STATE_GONE,
                    attention_required=False,
                    resource_exists=False,
                    primary_reason="NotFound",
                ),
            )

        truncated = truncate_target_group_status(payload)
        redacted = redact_output(truncated)

        return ToolResult(
            summary=(
                f"target group {target_group_name} is {_summary_state(redacted)}: "
                f"healthy={redacted.get('healthy_count', 0)}, "
                f"unhealthy={redacted.get('unhealthy_count', 0)}, "
                f"initial={redacted.get('initial_count', 0)}, "
                f"draining={redacted.get('draining_count', 0)}, "
                f"unused={redacted.get('unused_count', 0)}, "
                f"target_type={redacted.get('target_type')}, "
                f"protocol={redacted.get('protocol')}, "
                f"port={redacted.get('port')}, "
                f"vpc_id={redacted.get('vpc_id')}"
            ),
            evidence=[redacted],
            metadata=_build_target_group_metadata(redacted),
        )


def _summary_state(payload: dict[str, object]) -> str:
    metadata = _build_target_group_metadata(payload)
    health_state = metadata["health_state"]
    if health_state == HEALTH_STATE_HEALTHY:
        return "healthy"
    if health_state == HEALTH_STATE_FAILED:
        return "failed"
    return "degraded"


def _build_target_group_metadata(payload: dict[str, object]) -> dict[str, object]:
    healthy = int(payload.get("healthy_count", 0) or 0)
    unhealthy = int(payload.get("unhealthy_count", 0) or 0)
    initial = int(payload.get("initial_count", 0) or 0)
    draining = int(payload.get("draining_count", 0) or 0)
    unused = int(payload.get("unused_count", 0) or 0)

    if unhealthy > 0:
        return make_investigation_metadata(
            health_state=HEALTH_STATE_FAILED,
            attention_required=True,
            resource_exists=True,
            primary_reason="UnhealthyTargets",
        )
    if initial > 0 or draining > 0 or (healthy == 0 and unused > 0):
        primary_reason = "UnusedTargets" if healthy == 0 and unused > 0 else "TargetsTransitioning"
        return make_investigation_metadata(
            health_state=HEALTH_STATE_DEGRADED,
            attention_required=True,
            resource_exists=True,
            primary_reason=primary_reason,
        )
    return make_investigation_metadata(
        health_state=HEALTH_STATE_HEALTHY,
        attention_required=False,
        resource_exists=True,
        primary_reason="HealthyTargets",
    )
