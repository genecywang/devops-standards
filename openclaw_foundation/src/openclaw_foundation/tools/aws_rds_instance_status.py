from openclaw_foundation.adapters.aws import AwsProviderAdapter, AwsResourceNotFoundError
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult
from openclaw_foundation.runtime.guards import redact_output, truncate_rds_instance_status
from openclaw_foundation.tools.investigation_metadata import (
    HEALTH_STATE_DEGRADED,
    HEALTH_STATE_FAILED,
    HEALTH_STATE_GONE,
    HEALTH_STATE_HEALTHY,
    make_investigation_metadata,
)

_DEGRADED_STATUSES = frozenset({"modifying", "backing-up", "starting", "stopping"})
_FAILED_STATUSES = frozenset(
    {
        "failed",
        "deleting",
        "incompatible-parameters",
        "incompatible-restore",
        "incompatible-network",
        "incompatible-option-group",
        "storage-full",
    }
)


class AwsRdsInstanceStatusTool:
    tool_name = "get_rds_instance_status"
    supported_request_types = ("investigation",)

    def __init__(self, adapter: AwsProviderAdapter) -> None:
        self._adapter = adapter

    def invoke(self, request: InvestigationRequest) -> ToolResult:
        if request.target is None:
            raise ValueError("target is required for get_rds_instance_status")

        region_code = str(request.scope.get("region_code") or "").strip()
        if not region_code:
            raise ValueError("scope.region_code is required for get_rds_instance_status")

        db_instance_identifier = request.target.get("resource_name") or request.target.get("db_instance_identifier")
        if db_instance_identifier is None:
            raise ValueError("resource_name or db_instance_identifier is required for get_rds_instance_status")

        try:
            payload = self._adapter.get_rds_instance_status(region_code, db_instance_identifier)
        except AwsResourceNotFoundError:
            return ToolResult(
                summary=f"rds instance {db_instance_identifier} does not exist in region {region_code}",
                evidence=[],
                metadata=make_investigation_metadata(
                    health_state=HEALTH_STATE_GONE,
                    attention_required=False,
                    resource_exists=False,
                    primary_reason="NotFound",
                ),
            )

        truncated = truncate_rds_instance_status(payload)
        redacted = redact_output(truncated)
        status = str(redacted.get("status") or "unknown")
        endpoint_address = str(redacted.get("endpoint_address") or "").strip()

        return ToolResult(
            summary=(
                f"rds instance {db_instance_identifier} is {status}: "
                f"engine={redacted.get('engine')}, "
                f"engine_version={redacted.get('engine_version')}, "
                f"class={redacted.get('instance_class')}, "
                f"multi_az={'true' if redacted.get('multi_az') else 'false'}, "
                f"endpoint={'present' if endpoint_address else 'missing'}"
            ),
            evidence=[redacted],
            metadata=_build_rds_metadata(status),
        )


def _build_rds_metadata(status: str) -> dict[str, object]:
    normalized = status.lower()
    if normalized == "available":
        return make_investigation_metadata(
            health_state=HEALTH_STATE_HEALTHY,
            attention_required=False,
            resource_exists=True,
            primary_reason=status,
        )
    if normalized in _DEGRADED_STATUSES:
        return make_investigation_metadata(
            health_state=HEALTH_STATE_DEGRADED,
            attention_required=True,
            resource_exists=True,
            primary_reason=status,
        )
    if normalized in _FAILED_STATUSES:
        return make_investigation_metadata(
            health_state=HEALTH_STATE_FAILED,
            attention_required=True,
            resource_exists=True,
            primary_reason=status,
        )
    return make_investigation_metadata(
        health_state=HEALTH_STATE_DEGRADED,
        attention_required=True,
        resource_exists=True,
        primary_reason=status or "unknown",
    )
