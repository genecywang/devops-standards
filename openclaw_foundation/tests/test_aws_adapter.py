from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from openclaw_foundation.adapters.aws import (
    AwsAccessDeniedError,
    AwsApiError,
    AwsConfigError,
    AwsError,
    AwsResourceNotFoundError,
    FakeAwsProviderAdapter,
    RealAwsProviderAdapter,
)


def test_aws_domain_errors_share_common_base() -> None:
    assert issubclass(AwsConfigError, AwsError)
    assert issubclass(AwsAccessDeniedError, AwsError)
    assert issubclass(AwsResourceNotFoundError, AwsError)
    assert issubclass(AwsApiError, AwsError)


def test_fake_adapter_returns_bounded_rds_payload() -> None:
    adapter = FakeAwsProviderAdapter()

    result = adapter.get_rds_instance_status(
        region_code="ap-northeast-1",
        db_instance_identifier="shuriken",
    )

    assert result["db_instance_identifier"] == "shuriken"
    assert result["status"] == "available"
    assert result["engine"] == "postgres"


def test_fake_adapter_returns_bounded_target_group_payload() -> None:
    adapter = FakeAwsProviderAdapter()

    result = adapter.get_target_group_status(
        region_code="ap-northeast-1",
        target_group_name="targetgroup/api/abc123",
    )

    assert result["target_group_name"] == "targetgroup/api/abc123"
    assert result["healthy_count"] == 2
    assert result["unhealthy_count"] == 0


def test_real_adapter_maps_rds_instance_payload() -> None:
    client = Mock()
    client.describe_db_instances.return_value = {
        "DBInstances": [
            {
                "DBInstanceIdentifier": "shuriken",
                "DBInstanceStatus": "available",
                "Engine": "postgres",
                "EngineVersion": "16.3",
                "DBInstanceClass": "db.t4g.medium",
                "MultiAZ": True,
                "Endpoint": {"Address": "shuriken.abc.ap-northeast-1.rds.amazonaws.com", "Port": 5432},
            }
        ]
    }
    adapter = RealAwsProviderAdapter(client_factory=Mock(return_value=client))

    result = adapter.get_rds_instance_status(
        region_code="ap-northeast-1",
        db_instance_identifier="shuriken",
    )

    assert result == {
        "db_instance_identifier": "shuriken",
        "status": "available",
        "engine": "postgres",
        "engine_version": "16.3",
        "instance_class": "db.t4g.medium",
        "multi_az": True,
        "endpoint_address": "shuriken.abc.ap-northeast-1.rds.amazonaws.com",
        "endpoint_port": 5432,
    }


def test_real_adapter_maps_target_group_payload() -> None:
    elbv2_client = Mock()
    elbv2_client.describe_target_groups.return_value = {
        "TargetGroups": [
            {
                "TargetGroupName": "k8s-prod-api",
                "TargetGroupArn": "arn:aws:elasticloadbalancing:ap-northeast-1:123:targetgroup/k8s-prod-api/abc123",
                "TargetType": "ip",
                "Protocol": "HTTP",
                "Port": 8080,
                "VpcId": "vpc-12345",
            }
        ]
    }
    elbv2_client.describe_target_health.return_value = {
        "TargetHealthDescriptions": [
            {"TargetHealth": {"State": "healthy"}},
            {"TargetHealth": {"State": "healthy"}},
            {"TargetHealth": {"State": "draining"}},
        ]
    }
    adapter = RealAwsProviderAdapter(client_factory=Mock(return_value=elbv2_client))

    result = adapter.get_target_group_status(
        region_code="ap-northeast-1",
        target_group_name="targetgroup/k8s-prod-api/abc123",
    )

    assert result == {
        "target_group_name": "targetgroup/k8s-prod-api/abc123",
        "target_group_arn": "arn:aws:elasticloadbalancing:ap-northeast-1:123:targetgroup/k8s-prod-api/abc123",
        "target_type": "ip",
        "protocol": "HTTP",
        "port": 8080,
        "vpc_id": "vpc-12345",
        "healthy_count": 2,
        "unhealthy_count": 0,
        "initial_count": 0,
        "draining_count": 1,
        "unused_count": 0,
    }


def test_real_adapter_maps_missing_rds_instance_to_domain_error() -> None:
    client = Mock()
    client.describe_db_instances.return_value = {"DBInstances": []}
    adapter = RealAwsProviderAdapter(client_factory=Mock(return_value=client))

    with pytest.raises(AwsResourceNotFoundError, match="rds instance not found"):
        adapter.get_rds_instance_status(
            region_code="ap-northeast-1",
            db_instance_identifier="shuriken",
        )


def test_real_adapter_maps_missing_target_group_to_domain_error() -> None:
    client = Mock()
    client.describe_target_groups.return_value = {"TargetGroups": []}
    adapter = RealAwsProviderAdapter(client_factory=Mock(return_value=client))

    with pytest.raises(AwsResourceNotFoundError, match="target group not found"):
        adapter.get_target_group_status(
            region_code="ap-northeast-1",
            target_group_name="targetgroup/api/abc123",
        )


def test_real_adapter_maps_access_denied_client_error() -> None:
    class FakeClientError(Exception):
        def __init__(self) -> None:
            self.response = {"Error": {"Code": "AccessDeniedException"}}

    adapter = RealAwsProviderAdapter(
        client_factory=Mock(
            return_value=SimpleNamespace(
                describe_db_instances=Mock(side_effect=FakeClientError())
            )
        ),
        client_error_cls=FakeClientError,
    )

    with pytest.raises(AwsAccessDeniedError, match="aws access denied"):
        adapter.get_rds_instance_status(
            region_code="ap-northeast-1",
            db_instance_identifier="shuriken",
        )
