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


def test_real_adapter_maps_missing_rds_instance_to_domain_error() -> None:
    client = Mock()
    client.describe_db_instances.return_value = {"DBInstances": []}
    adapter = RealAwsProviderAdapter(client_factory=Mock(return_value=client))

    with pytest.raises(AwsResourceNotFoundError, match="rds instance not found"):
        adapter.get_rds_instance_status(
            region_code="ap-northeast-1",
            db_instance_identifier="shuriken",
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

