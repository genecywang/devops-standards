from __future__ import annotations

from typing import Any, Protocol

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - exercised via real provider setup
    boto3 = None
    ClientError = None


class AwsError(RuntimeError):
    pass


class AwsConfigError(AwsError):
    pass


class AwsAccessDeniedError(AwsError):
    pass


class AwsResourceNotFoundError(AwsError):
    pass


class AwsApiError(AwsError):
    pass


class AwsProviderAdapter(Protocol):
    def get_rds_instance_status(self, region_code: str, db_instance_identifier: str) -> dict[str, object]: ...


def build_rds_client(region_code: str) -> Any:
    if boto3 is None:
        raise AwsConfigError("boto3 dependency is not installed")
    return boto3.client("rds", region_name=region_code)


class FakeAwsProviderAdapter:
    def get_rds_instance_status(
        self,
        region_code: str,
        db_instance_identifier: str,
    ) -> dict[str, object]:
        return {
            "db_instance_identifier": db_instance_identifier,
            "status": "available",
            "engine": "postgres",
            "engine_version": "16.3",
            "instance_class": "db.t4g.medium",
            "multi_az": True,
            "endpoint_address": f"{db_instance_identifier}.abc.{region_code}.rds.amazonaws.com",
            "endpoint_port": 5432,
        }


class RealAwsProviderAdapter:
    def __init__(
        self,
        client_factory=build_rds_client,
        client_error_cls=ClientError,
    ) -> None:
        self._client_factory = client_factory
        self._client_error_cls = client_error_cls

    def get_rds_instance_status(
        self,
        region_code: str,
        db_instance_identifier: str,
    ) -> dict[str, object]:
        try:
            client = self._client_factory(region_code)
            response = client.describe_db_instances(DBInstanceIdentifier=db_instance_identifier)
        except Exception as error:
            if self._client_error_cls is not None and isinstance(error, self._client_error_cls):
                code = str(getattr(error, "response", {}).get("Error", {}).get("Code") or "")
                if code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation"}:
                    raise AwsAccessDeniedError("aws access denied") from error
                if code in {"DBInstanceNotFound", "DBInstanceNotFoundFault"}:
                    raise AwsResourceNotFoundError("rds instance not found") from error
                raise AwsApiError("failed to describe rds instance") from error
            if isinstance(error, AwsError):
                raise
            raise AwsApiError("failed to describe rds instance") from error

        instances = response.get("DBInstances", [])
        if not instances:
            raise AwsResourceNotFoundError("rds instance not found")

        instance = instances[0]
        endpoint = instance.get("Endpoint") or {}
        return {
            "db_instance_identifier": str(instance.get("DBInstanceIdentifier") or db_instance_identifier),
            "status": str(instance.get("DBInstanceStatus") or "unknown"),
            "engine": str(instance.get("Engine") or "unknown"),
            "engine_version": str(instance.get("EngineVersion") or "unknown"),
            "instance_class": str(instance.get("DBInstanceClass") or "unknown"),
            "multi_az": bool(instance.get("MultiAZ", False)),
            "endpoint_address": str(endpoint.get("Address") or ""),
            "endpoint_port": endpoint.get("Port"),
        }
