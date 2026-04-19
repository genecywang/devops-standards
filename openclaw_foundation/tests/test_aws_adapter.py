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


def test_fake_adapter_returns_bounded_load_balancer_payload() -> None:
    adapter = FakeAwsProviderAdapter()

    result = adapter.get_load_balancer_status(
        region_code="ap-northeast-1",
        load_balancer_name="app/prod-api/abc123",
    )

    assert result["load_balancer_name"] == "app/prod-api/abc123"
    assert result["scheme"] == "internet-facing"
    assert result["state"] == "active"


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
    adapter = RealAwsProviderAdapter(rds_client_factory=Mock(return_value=client))

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
    elbv2_client.describe_tags.return_value = {"TagDescriptions": []}
    adapter = RealAwsProviderAdapter(elbv2_client_factory=Mock(return_value=elbv2_client))

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
        "target_ips": [],
        "k8s_controller_tags": {},
    }


def test_real_adapter_returns_target_ips_and_controller_tags() -> None:
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
            {"Target": {"Id": "10.0.1.10"}, "TargetHealth": {"State": "healthy"}},
            {"Target": {"Id": "10.0.1.11"}, "TargetHealth": {"State": "healthy"}},
            {"Target": {"Id": "i-abc123"}, "TargetHealth": {"State": "draining"}},
        ]
    }
    elbv2_client.describe_tags.return_value = {
        "TagDescriptions": [
            {
                "ResourceArn": "arn:aws:elasticloadbalancing:ap-northeast-1:123:targetgroup/k8s-prod-api/abc123",
                "Tags": [
                    {"Key": "elbv2.k8s.aws/cluster", "Value": "prod-cluster"},
                    {"Key": "service.k8s.aws/resource", "Value": "service"},
                    {"Key": "service.k8s.aws/stack", "Value": "prod/service"},
                ],
            }
        ]
    }
    adapter = RealAwsProviderAdapter(elbv2_client_factory=Mock(return_value=elbv2_client))

    result = adapter.get_target_group_status(
        region_code="ap-northeast-1",
        target_group_name="targetgroup/k8s-prod-api/abc123",
    )

    assert result["target_ips"] == ["10.0.1.10", "10.0.1.11"]
    assert result["k8s_controller_tags"] == {
        "elbv2.k8s.aws/cluster": "prod-cluster",
        "service.k8s.aws/resource": "service",
        "service.k8s.aws/stack": "prod/service",
    }


def test_real_adapter_returns_empty_controller_tags_when_describe_tags_fails() -> None:
    class FakeClientError(Exception):
        def __init__(self) -> None:
            self.response = {"Error": {"Code": "AccessDeniedException"}}

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
            {"Target": {"Id": "10.0.1.10"}, "TargetHealth": {"State": "healthy"}}
        ]
    }
    elbv2_client.describe_tags.side_effect = FakeClientError()
    adapter = RealAwsProviderAdapter(
        elbv2_client_factory=Mock(return_value=elbv2_client),
        client_error_cls=FakeClientError,
    )

    result = adapter.get_target_group_status(
        region_code="ap-northeast-1",
        target_group_name="targetgroup/k8s-prod-api/abc123",
    )

    assert result["target_ips"] == ["10.0.1.10"]
    assert result["k8s_controller_tags"] == {}


def test_real_adapter_ignores_target_ips_for_non_ip_target_type() -> None:
    elbv2_client = Mock()
    elbv2_client.describe_target_groups.return_value = {
        "TargetGroups": [
            {
                "TargetGroupName": "k8s-prod-api",
                "TargetGroupArn": "arn:aws:elasticloadbalancing:ap-northeast-1:123:targetgroup/k8s-prod-api/abc123",
                "TargetType": "instance",
                "Protocol": "HTTP",
                "Port": 8080,
                "VpcId": "vpc-12345",
            }
        ]
    }
    elbv2_client.describe_target_health.return_value = {
        "TargetHealthDescriptions": [
            {"Target": {"Id": "10.0.1.10"}, "TargetHealth": {"State": "healthy"}},
            {"Target": {"Id": "10.0.1.11"}, "TargetHealth": {"State": "draining"}},
        ]
    }
    elbv2_client.describe_tags.return_value = {"TagDescriptions": []}
    adapter = RealAwsProviderAdapter(elbv2_client_factory=Mock(return_value=elbv2_client))

    result = adapter.get_target_group_status(
        region_code="ap-northeast-1",
        target_group_name="targetgroup/k8s-prod-api/abc123",
    )

    assert result["target_type"] == "instance"
    assert result["target_ips"] == []


def test_real_adapter_raises_api_error_when_describe_tags_raises_non_client_error() -> None:
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
            {"Target": {"Id": "10.0.1.10"}, "TargetHealth": {"State": "healthy"}}
        ]
    }
    elbv2_client.describe_tags.side_effect = ValueError("boom")
    adapter = RealAwsProviderAdapter(elbv2_client_factory=Mock(return_value=elbv2_client))

    with pytest.raises(AwsApiError, match="failed to describe target group tags"):
        adapter.get_target_group_status(
            region_code="ap-northeast-1",
            target_group_name="targetgroup/k8s-prod-api/abc123",
        )


def test_real_adapter_maps_load_balancer_payload() -> None:
    elbv2_client = Mock()
    elbv2_client.describe_load_balancers.return_value = {
        "LoadBalancers": [
            {
                "LoadBalancerName": "prod-api",
                "LoadBalancerArn": "arn:aws:elasticloadbalancing:ap-northeast-1:123:loadbalancer/app/prod-api/abc123",
                "DNSName": "prod-api-123.ap-northeast-1.elb.amazonaws.com",
                "Scheme": "internet-facing",
                "Type": "application",
                "VpcId": "vpc-12345",
                "State": {"Code": "active"},
                "AvailabilityZones": [{"ZoneName": "apne1-a"}, {"ZoneName": "apne1-c"}],
                "SecurityGroups": ["sg-1", "sg-2"],
            }
        ]
    }
    adapter = RealAwsProviderAdapter(elbv2_client_factory=Mock(return_value=elbv2_client))

    result = adapter.get_load_balancer_status(
        region_code="ap-northeast-1",
        load_balancer_name="app/prod-api/abc123",
    )

    assert result == {
        "load_balancer_name": "app/prod-api/abc123",
        "load_balancer_arn": "arn:aws:elasticloadbalancing:ap-northeast-1:123:loadbalancer/app/prod-api/abc123",
        "dns_name": "prod-api-123.ap-northeast-1.elb.amazonaws.com",
        "scheme": "internet-facing",
        "type": "application",
        "state": "active",
        "vpc_id": "vpc-12345",
        "availability_zone_count": 2,
        "security_group_count": 2,
    }


def test_real_adapter_maps_missing_rds_instance_to_domain_error() -> None:
    client = Mock()
    client.describe_db_instances.return_value = {"DBInstances": []}
    adapter = RealAwsProviderAdapter(rds_client_factory=Mock(return_value=client))

    with pytest.raises(AwsResourceNotFoundError, match="rds instance not found"):
        adapter.get_rds_instance_status(
            region_code="ap-northeast-1",
            db_instance_identifier="shuriken",
        )


def test_real_adapter_maps_missing_target_group_to_domain_error() -> None:
    client = Mock()
    client.describe_target_groups.return_value = {"TargetGroups": []}
    adapter = RealAwsProviderAdapter(elbv2_client_factory=Mock(return_value=client))

    with pytest.raises(AwsResourceNotFoundError, match="target group not found"):
        adapter.get_target_group_status(
            region_code="ap-northeast-1",
            target_group_name="targetgroup/api/abc123",
        )


def test_real_adapter_maps_missing_load_balancer_to_domain_error() -> None:
    client = Mock()
    client.describe_load_balancers.return_value = {"LoadBalancers": []}
    adapter = RealAwsProviderAdapter(elbv2_client_factory=Mock(return_value=client))

    with pytest.raises(AwsResourceNotFoundError, match="load balancer not found"):
        adapter.get_load_balancer_status(
            region_code="ap-northeast-1",
            load_balancer_name="app/prod-api/abc123",
        )


def test_real_adapter_maps_access_denied_client_error() -> None:
    class FakeClientError(Exception):
        def __init__(self) -> None:
            self.response = {"Error": {"Code": "AccessDeniedException"}}

    adapter = RealAwsProviderAdapter(
        rds_client_factory=Mock(
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


def test_real_adapter_uses_elbv2_factory_for_load_balancer_calls() -> None:
    rds_factory = Mock()
    elbv2_client = Mock()
    elbv2_client.describe_load_balancers.return_value = {
        "LoadBalancers": [
            {
                "LoadBalancerArn": "arn:aws:elasticloadbalancing:ap-northeast-1:123:loadbalancer/app/prod-api/abc123",
                "DNSName": "prod-api-123.ap-northeast-1.elb.amazonaws.com",
                "Scheme": "internet-facing",
                "Type": "application",
                "VpcId": "vpc-12345",
                "State": {"Code": "active"},
                "AvailabilityZones": [{"ZoneName": "apne1-a"}],
                "SecurityGroups": ["sg-1"],
            }
        ]
    }
    elbv2_factory = Mock(return_value=elbv2_client)
    adapter = RealAwsProviderAdapter(
        rds_client_factory=rds_factory,
        elbv2_client_factory=elbv2_factory,
    )

    result = adapter.get_load_balancer_status(
        region_code="ap-northeast-1",
        load_balancer_name="app/prod-api/abc123",
    )

    rds_factory.assert_not_called()
    elbv2_factory.assert_called_once_with("ap-northeast-1")
    assert result["state"] == "active"
