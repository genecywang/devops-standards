from unittest.mock import Mock

from openclaw_foundation.adapters.aws import AwsResourceNotFoundError, FakeAwsProviderAdapter
from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.runtime.guards import truncate_target_group_status
from openclaw_foundation.tools.aws_target_group_status import AwsTargetGroupStatusTool


def make_request(resource_name: str = "targetgroup/api/abc123") -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-tg-001",
        source_product="alert_auto_investigator",
        scope={
            "environment": "prod-jp",
            "cluster": "",
            "region_code": "ap-northeast-1",
        },
        input_ref="fixture:target-group-status",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=30,
            max_output_tokens=256,
        ),
        tool_name="get_target_group_status",
        target={
            "cluster": "",
            "namespace": "",
            "resource_name": resource_name,
        },
    )


def test_get_target_group_status_tool_returns_summary_and_metadata() -> None:
    tool = AwsTargetGroupStatusTool(adapter=FakeAwsProviderAdapter())

    result = tool.invoke(make_request())

    assert result.summary == (
        "target group targetgroup/api/abc123 is healthy: healthy=2, unhealthy=0, initial=0, "
        "draining=0, unused=0, target_type=ip, protocol=HTTP, port=8080, vpc_id=vpc-12345"
    )
    assert result.metadata == {
        "health_state": "healthy",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "HealthyTargets",
    }


def test_get_target_group_status_tool_marks_unhealthy_targets_as_failed() -> None:
    adapter = Mock()
    adapter.get_target_group_status.return_value = {
        "target_group_name": "targetgroup/api/abc123",
        "target_group_arn": "arn:aws:elasticloadbalancing:ap-northeast-1:123:targetgroup/api/abc123",
        "target_type": "ip",
        "protocol": "HTTP",
        "port": 8080,
        "vpc_id": "vpc-12345",
        "healthy_count": 1,
        "unhealthy_count": 2,
        "initial_count": 0,
        "draining_count": 0,
        "unused_count": 0,
    }
    tool = AwsTargetGroupStatusTool(adapter=adapter)

    result = tool.invoke(make_request())

    assert result.metadata == {
        "health_state": "failed",
        "attention_required": True,
        "resource_exists": True,
        "primary_reason": "UnhealthyTargets",
    }


def test_get_target_group_status_tool_handles_missing_target_group() -> None:
    adapter = Mock()
    adapter.get_target_group_status.side_effect = AwsResourceNotFoundError("target group not found")
    tool = AwsTargetGroupStatusTool(adapter=adapter)

    result = tool.invoke(make_request())

    assert result.summary == "target group targetgroup/api/abc123 does not exist in region ap-northeast-1"
    assert result.metadata == {
        "health_state": "gone",
        "attention_required": False,
        "resource_exists": False,
        "primary_reason": "NotFound",
    }


def test_truncate_target_group_status_keeps_only_bounded_evidence_fields() -> None:
    long_tag_value = "x" * 300
    payload = {
        "target_group_name": "targetgroup/api/abc123",
        "target_group_arn": "arn:aws:elasticloadbalancing:ap-northeast-1:123:targetgroup/api/abc123",
        "target_type": "ip",
        "protocol": "HTTP",
        "port": 8080,
        "vpc_id": "vpc-12345",
        "healthy_count": 2,
        "unhealthy_count": 0,
        "initial_count": 0,
        "draining_count": 0,
        "unused_count": 0,
        "target_ips": [f"10.0.1.{idx}" for idx in range(25)],
        "k8s_controller_tags": {
            "elbv2.k8s.aws/cluster": "prod-cluster",
            "service.k8s.aws/resource": "service",
            "service.k8s.aws/stack": long_tag_value,
            "ignored.tag/key": "drop-me",
        },
        "unexpected": "drop-me",
    }

    result = truncate_target_group_status(payload)

    assert result == {
        "target_group_name": "targetgroup/api/abc123",
        "target_group_arn": "arn:aws:elasticloadbalancing:ap-northeast-1:123:targetgroup/api/abc123",
        "target_type": "ip",
        "protocol": "HTTP",
        "port": 8080,
        "vpc_id": "vpc-12345",
        "healthy_count": 2,
        "unhealthy_count": 0,
        "initial_count": 0,
        "draining_count": 0,
        "unused_count": 0,
        "target_ips": [f"10.0.1.{idx}" for idx in range(20)],
        "k8s_controller_tags": {
            "elbv2.k8s.aws/cluster": "prod-cluster",
            "service.k8s.aws/resource": "service",
            "service.k8s.aws/stack": "x" * 256 + "...[truncated]",
        },
    }

    assert len(result["target_ips"]) == 20
