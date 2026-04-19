from unittest.mock import Mock

from openclaw_foundation.adapters.aws import AwsResourceNotFoundError, FakeAwsProviderAdapter
from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.tools.aws_rds_instance_status import AwsRdsInstanceStatusTool


def make_request(resource_name: str = "shuriken") -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-rds-001",
        source_product="alert_auto_investigator",
        scope={
            "environment": "prod-jp",
            "cluster": "",
            "region_code": "ap-northeast-1",
        },
        input_ref="fixture:rds-status",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=30,
            max_output_tokens=256,
        ),
        tool_name="get_rds_instance_status",
        target={
            "cluster": "",
            "namespace": "",
            "resource_name": resource_name,
        },
    )


def test_get_rds_instance_status_tool_returns_summary_and_metadata() -> None:
    tool = AwsRdsInstanceStatusTool(adapter=FakeAwsProviderAdapter())

    result = tool.invoke(make_request())

    assert result.summary == (
        "rds instance shuriken is available: engine=postgres, engine_version=16.3, "
        "class=db.t4g.medium, multi_az=true, endpoint=present"
    )
    assert result.metadata == {
        "health_state": "healthy",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "available",
    }
    assert result.evidence == [
        {
            "db_instance_identifier": "shuriken",
            "status": "available",
            "engine": "postgres",
            "engine_version": "16.3",
            "instance_class": "db.t4g.medium",
            "multi_az": True,
            "endpoint_address": "shuriken.abc.ap-northeast-1.rds.amazonaws.com",
            "endpoint_port": 5432,
        }
    ]


def test_get_rds_instance_status_tool_marks_non_available_status_for_attention() -> None:
    adapter = Mock()
    adapter.get_rds_instance_status.return_value = {
        "db_instance_identifier": "shuriken",
        "status": "modifying",
        "engine": "postgres",
        "engine_version": "16.3",
        "instance_class": "db.t4g.medium",
        "multi_az": False,
        "endpoint_address": "shuriken.abc.ap-northeast-1.rds.amazonaws.com",
        "endpoint_port": 5432,
    }
    tool = AwsRdsInstanceStatusTool(adapter=adapter)

    result = tool.invoke(make_request())

    assert result.metadata == {
        "health_state": "degraded",
        "attention_required": True,
        "resource_exists": True,
        "primary_reason": "modifying",
    }


def test_get_rds_instance_status_tool_handles_missing_instance() -> None:
    adapter = Mock()
    adapter.get_rds_instance_status.side_effect = AwsResourceNotFoundError("rds instance not found")
    tool = AwsRdsInstanceStatusTool(adapter=adapter)

    result = tool.invoke(make_request())

    assert result.summary == "rds instance shuriken does not exist in region ap-northeast-1"
    assert result.metadata == {
        "health_state": "gone",
        "attention_required": False,
        "resource_exists": False,
        "primary_reason": "NotFound",
    }
    assert result.evidence == []
