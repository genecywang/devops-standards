from unittest.mock import Mock

from openclaw_foundation.adapters.aws import AwsResourceNotFoundError, FakeAwsProviderAdapter
from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.tools.aws_load_balancer_status import AwsLoadBalancerStatusTool


def make_request(resource_name: str = "app/prod-api/abc123") -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-lb-001",
        source_product="alert_auto_investigator",
        scope={
            "environment": "prod-jp",
            "cluster": "",
            "region_code": "ap-northeast-1",
        },
        input_ref="fixture:load-balancer-status",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=30,
            max_output_tokens=256,
        ),
        tool_name="get_load_balancer_status",
        target={
            "cluster": "",
            "namespace": "",
            "resource_name": resource_name,
        },
    )


def test_get_load_balancer_status_tool_returns_summary_and_metadata() -> None:
    tool = AwsLoadBalancerStatusTool(adapter=FakeAwsProviderAdapter())

    result = tool.invoke(make_request())

    assert result.summary == (
        "load balancer app/prod-api/abc123 is active: type=application, scheme=internet-facing, "
        "state=active, vpc_id=vpc-12345, availability_zones=2, security_groups=2"
    )
    assert result.metadata == {
        "health_state": "healthy",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "active",
    }


def test_get_load_balancer_status_tool_marks_provisioning_as_degraded() -> None:
    adapter = Mock()
    adapter.get_load_balancer_status.return_value = {
        "load_balancer_name": "app/prod-api/abc123",
        "load_balancer_arn": "arn:aws:elasticloadbalancing:ap-northeast-1:123:loadbalancer/app/prod-api/abc123",
        "dns_name": "prod-api-123.ap-northeast-1.elb.amazonaws.com",
        "scheme": "internet-facing",
        "type": "application",
        "state": "provisioning",
        "vpc_id": "vpc-12345",
        "availability_zone_count": 2,
        "security_group_count": 2,
    }
    tool = AwsLoadBalancerStatusTool(adapter=adapter)

    result = tool.invoke(make_request())

    assert result.metadata == {
        "health_state": "degraded",
        "attention_required": True,
        "resource_exists": True,
        "primary_reason": "provisioning",
    }


def test_get_load_balancer_status_tool_handles_missing_load_balancer() -> None:
    adapter = Mock()
    adapter.get_load_balancer_status.side_effect = AwsResourceNotFoundError("load balancer not found")
    tool = AwsLoadBalancerStatusTool(adapter=adapter)

    result = tool.invoke(make_request())

    assert result.summary == "load balancer app/prod-api/abc123 does not exist in region ap-northeast-1"
    assert result.metadata == {
        "health_state": "gone",
        "attention_required": False,
        "resource_exists": False,
        "primary_reason": "NotFound",
    }
