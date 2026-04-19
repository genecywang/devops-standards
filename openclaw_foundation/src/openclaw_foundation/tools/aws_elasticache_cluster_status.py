from __future__ import annotations

from collections import Counter

from openclaw_foundation.adapters.aws import (
    AwsAccessDeniedError,
    AwsApiError,
    AwsProviderAdapter,
    AwsResourceNotFoundError,
)
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult
from openclaw_foundation.runtime.guards import redact_output, truncate_elasticache_cluster_status
from openclaw_foundation.tools.investigation_metadata import (
    HEALTH_STATE_DEGRADED,
    HEALTH_STATE_FAILED,
    HEALTH_STATE_GONE,
    HEALTH_STATE_HEALTHY,
    HEALTH_STATE_IN_PROGRESS,
    make_investigation_metadata,
)

_IN_PROGRESS_STATUSES = frozenset({"creating", "snapshotting"})
_DEGRADED_STATUSES = frozenset({"modifying", "rebooting cluster nodes"})


class AwsElastiCacheClusterStatusTool:
    tool_name = "get_elasticache_cluster_status"
    supported_request_types = ("investigation",)

    def __init__(self, adapter: AwsProviderAdapter) -> None:
        self._adapter = adapter

    def invoke(self, request: InvestigationRequest) -> ToolResult:
        if request.target is None:
            raise ValueError("target is required for get_elasticache_cluster_status")

        region_code = str(request.scope.get("region_code") or "").strip()
        if not region_code:
            raise ValueError("scope.region_code is required for get_elasticache_cluster_status")

        cache_cluster_id = request.target.get("resource_name") or request.target.get("cache_cluster_id")
        if cache_cluster_id is None:
            raise ValueError(
                "resource_name or cache_cluster_id is required for get_elasticache_cluster_status"
            )

        try:
            payload = self._adapter.get_elasticache_cluster_status(region_code, cache_cluster_id)
        except AwsResourceNotFoundError:
            return ToolResult(
                summary=f"elasticache cluster {cache_cluster_id} does not exist in region {region_code}",
                evidence=[],
                metadata=make_investigation_metadata(
                    health_state=HEALTH_STATE_GONE,
                    attention_required=False,
                    resource_exists=False,
                    primary_reason="NotFound",
                ),
            )
        except AwsAccessDeniedError:
            return _inspection_error_result(
                cache_cluster_id=cache_cluster_id,
                region_code=region_code,
                reason="aws access denied",
                primary_reason="AccessDenied",
            )
        except AwsApiError as error:
            return _inspection_error_result(
                cache_cluster_id=cache_cluster_id,
                region_code=region_code,
                reason=str(error) or "aws api error",
                primary_reason="AwsApiError",
            )

        truncated = truncate_elasticache_cluster_status(payload)
        redacted = redact_output(truncated)
        cluster_status = str(redacted.get("cache_cluster_status") or "unknown")
        replication_group_id = str(redacted.get("replication_group_id") or "").strip()

        return ToolResult(
            summary=(
                f"elasticache cluster {cache_cluster_id} is {cluster_status}: "
                f"engine={redacted.get('engine')}, "
                f"engine_version={redacted.get('engine_version')}, "
                f"nodes={redacted.get('num_cache_nodes')}, "
                f"node_statuses={_summarize_node_statuses(redacted.get('node_statuses'))}, "
                f"replication_group_id={'present' if replication_group_id else 'missing'}"
            ),
            evidence=[redacted],
            metadata=_build_elasticache_metadata(cluster_status, redacted.get("node_statuses")),
        )


def _inspection_error_result(
    *,
    cache_cluster_id: object,
    region_code: str,
    reason: str,
    primary_reason: str,
) -> ToolResult:
    return ToolResult(
        summary=(
            f"elasticache cluster {cache_cluster_id} could not be inspected in region {region_code}: "
            f"{reason}"
        ),
        evidence=[],
        metadata=make_investigation_metadata(
            health_state=HEALTH_STATE_FAILED,
            attention_required=True,
            resource_exists=True,
            primary_reason=primary_reason,
        ),
    )


def _build_elasticache_metadata(cluster_status: str, node_statuses: object) -> dict[str, object]:
    normalized = cluster_status.lower()
    if normalized == "available":
        if not _all_nodes_available(node_statuses):
            return make_investigation_metadata(
                health_state=HEALTH_STATE_DEGRADED,
                attention_required=True,
                resource_exists=True,
                primary_reason="NodeStatusMismatch",
            )
        return make_investigation_metadata(
            health_state=HEALTH_STATE_HEALTHY,
            attention_required=False,
            resource_exists=True,
            primary_reason=cluster_status,
        )
    if normalized in _IN_PROGRESS_STATUSES:
        return make_investigation_metadata(
            health_state=HEALTH_STATE_IN_PROGRESS,
            attention_required=True,
            resource_exists=True,
            primary_reason=cluster_status,
        )
    if normalized in _DEGRADED_STATUSES:
        return make_investigation_metadata(
            health_state=HEALTH_STATE_DEGRADED,
            attention_required=True,
            resource_exists=True,
            primary_reason=cluster_status,
        )
    return make_investigation_metadata(
        health_state=HEALTH_STATE_DEGRADED,
        attention_required=True,
        resource_exists=True,
        primary_reason=cluster_status or "unknown",
    )


def _all_nodes_available(node_statuses: object) -> bool:
    if not isinstance(node_statuses, list) or not node_statuses:
        return True
    return all(
        isinstance(node_status, dict)
        and str(node_status.get("cache_node_status") or "unknown").lower() == "available"
        for node_status in node_statuses
    )


def _summarize_node_statuses(raw_node_statuses: object) -> str:
    if not isinstance(raw_node_statuses, list) or not raw_node_statuses:
        return "none"

    counts = Counter(
        str(node_status.get("cache_node_status") or "unknown")
        for node_status in raw_node_statuses
        if isinstance(node_status, dict)
    )
    if not counts:
        return "none"
    return ", ".join(f"{status}={counts[status]}" for status in sorted(counts))
