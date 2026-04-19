from unittest.mock import Mock

from openclaw_foundation.adapters.aws import (
    AwsAccessDeniedError,
    AwsApiError,
    AwsResourceNotFoundError,
    FakeAwsProviderAdapter,
)
from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.runtime.guards import truncate_elasticache_cluster_status
from openclaw_foundation.tools.aws_elasticache_cluster_status import AwsElastiCacheClusterStatusTool


def make_request(resource_name: str = "prod-redis") -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-elasticache-001",
        source_product="alert_auto_investigator",
        scope={
            "environment": "prod-jp",
            "cluster": "",
            "region_code": "ap-northeast-1",
        },
        input_ref="fixture:elasticache-cluster-status",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=30,
            max_output_tokens=256,
        ),
        tool_name="get_elasticache_cluster_status",
        target={
            "cluster": "",
            "namespace": "",
            "resource_name": resource_name,
        },
    )


def test_get_elasticache_cluster_status_tool_returns_summary_and_metadata() -> None:
    tool = AwsElastiCacheClusterStatusTool(adapter=FakeAwsProviderAdapter())

    result = tool.invoke(make_request())

    assert result.summary == (
        "elasticache cluster prod-redis is available: engine=redis, engine_version=7.1, "
        "nodes=2, node_statuses=available=2, replication_group_id=present"
    )
    assert result.metadata == {
        "health_state": "healthy",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "available",
    }


def test_get_elasticache_cluster_status_tool_marks_available_with_non_available_node_as_degraded() -> None:
    adapter = Mock()
    adapter.get_elasticache_cluster_status.return_value = {
        "cache_cluster_id": "prod-redis",
        "replication_group_id": "prod-redis-rg",
        "engine": "redis",
        "engine_version": "7.1",
        "cache_cluster_status": "available",
        "num_cache_nodes": 2,
        "node_statuses": [
            {"cache_node_id": "0001", "cache_node_status": "available"},
            {"cache_node_id": "0002", "cache_node_status": "modifying"},
        ],
    }
    tool = AwsElastiCacheClusterStatusTool(adapter=adapter)

    result = tool.invoke(make_request())

    assert result.metadata == {
        "health_state": "degraded",
        "attention_required": True,
        "resource_exists": True,
        "primary_reason": "NodeStatusMismatch",
    }


def test_get_elasticache_cluster_status_tool_marks_creating_as_in_progress() -> None:
    adapter = Mock()
    adapter.get_elasticache_cluster_status.return_value = {
        "cache_cluster_id": "prod-redis",
        "replication_group_id": "prod-redis-rg",
        "engine": "redis",
        "engine_version": "7.1",
        "cache_cluster_status": "creating",
        "num_cache_nodes": 1,
        "node_statuses": [{"cache_node_id": "0001", "cache_node_status": "creating"}],
    }
    tool = AwsElastiCacheClusterStatusTool(adapter=adapter)

    result = tool.invoke(make_request())

    assert result.metadata == {
        "health_state": "in_progress",
        "attention_required": True,
        "resource_exists": True,
        "primary_reason": "creating",
    }


def test_get_elasticache_cluster_status_tool_marks_modifying_as_degraded() -> None:
    adapter = Mock()
    adapter.get_elasticache_cluster_status.return_value = {
        "cache_cluster_id": "prod-redis",
        "replication_group_id": "prod-redis-rg",
        "engine": "redis",
        "engine_version": "7.1",
        "cache_cluster_status": "modifying",
        "num_cache_nodes": 2,
        "node_statuses": [
            {"cache_node_id": "0001", "cache_node_status": "available"},
            {"cache_node_id": "0002", "cache_node_status": "modifying"},
        ],
    }
    tool = AwsElastiCacheClusterStatusTool(adapter=adapter)

    result = tool.invoke(make_request())

    assert result.metadata == {
        "health_state": "degraded",
        "attention_required": True,
        "resource_exists": True,
        "primary_reason": "modifying",
    }


def test_get_elasticache_cluster_status_tool_handles_missing_cluster() -> None:
    adapter = Mock()
    adapter.get_elasticache_cluster_status.side_effect = AwsResourceNotFoundError(
        "elasticache cluster not found"
    )
    tool = AwsElastiCacheClusterStatusTool(adapter=adapter)

    result = tool.invoke(make_request())

    assert result.summary == "elasticache cluster prod-redis does not exist in region ap-northeast-1"
    assert result.metadata == {
        "health_state": "gone",
        "attention_required": False,
        "resource_exists": False,
        "primary_reason": "NotFound",
    }


def test_get_elasticache_cluster_status_tool_handles_access_denied() -> None:
    adapter = Mock()
    adapter.get_elasticache_cluster_status.side_effect = AwsAccessDeniedError("aws access denied")
    tool = AwsElastiCacheClusterStatusTool(adapter=adapter)

    result = tool.invoke(make_request())

    assert result.summary == "elasticache cluster prod-redis could not be inspected in region ap-northeast-1: aws access denied"
    assert result.evidence == []
    assert result.metadata == {
        "health_state": "failed",
        "attention_required": True,
        "resource_exists": True,
        "primary_reason": "AccessDenied",
    }


def test_get_elasticache_cluster_status_tool_handles_api_error() -> None:
    adapter = Mock()
    adapter.get_elasticache_cluster_status.side_effect = AwsApiError(
        "failed to describe elasticache cluster"
    )
    tool = AwsElastiCacheClusterStatusTool(adapter=adapter)

    result = tool.invoke(make_request())

    assert result.summary == (
        "elasticache cluster prod-redis could not be inspected in region ap-northeast-1: "
        "failed to describe elasticache cluster"
    )
    assert result.evidence == []
    assert result.metadata == {
        "health_state": "failed",
        "attention_required": True,
        "resource_exists": True,
        "primary_reason": "AwsApiError",
    }


def test_truncate_elasticache_cluster_status_keeps_only_bounded_evidence_fields() -> None:
    payload = {
        "cache_cluster_id": "prod-redis",
        "replication_group_id": "prod-redis-rg",
        "engine": "redis",
        "engine_version": "7.1",
        "cache_cluster_status": "available",
        "num_cache_nodes": 2,
        "node_statuses": [
            {
                "cache_node_id": "0001",
                "cache_node_status": "available",
                "customer_outpost_arn": "drop-me",
            },
            {
                "cache_node_id": "0002",
                "cache_node_status": "available",
                "customer_availability_zone": "drop-me-too",
            },
        ],
        "unexpected": "drop-me",
    }

    result = truncate_elasticache_cluster_status(payload)

    assert result == {
        "cache_cluster_id": "prod-redis",
        "replication_group_id": "prod-redis-rg",
        "engine": "redis",
        "engine_version": "7.1",
        "cache_cluster_status": "available",
        "num_cache_nodes": 2,
        "node_statuses": [
            {"cache_node_id": "0001", "cache_node_status": "available"},
            {"cache_node_id": "0002", "cache_node_status": "available"},
        ],
    }


def test_truncate_elasticache_cluster_status_limits_node_statuses() -> None:
    payload = {
        "cache_cluster_id": "prod-redis",
        "engine": "redis",
        "engine_version": "7.1",
        "cache_cluster_status": "available",
        "num_cache_nodes": 25,
        "node_statuses": [
            {"cache_node_id": f"{idx:04d}", "cache_node_status": "available"}
            for idx in range(1, 26)
        ],
    }

    result = truncate_elasticache_cluster_status(payload)

    assert len(result["node_statuses"]) == 20
    assert result["node_statuses"][0] == {"cache_node_id": "0001", "cache_node_status": "available"}
    assert result["node_statuses"][-1] == {"cache_node_id": "0020", "cache_node_status": "available"}
