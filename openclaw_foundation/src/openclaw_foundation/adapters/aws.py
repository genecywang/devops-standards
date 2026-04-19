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
    def get_target_group_status(self, region_code: str, target_group_name: str) -> dict[str, object]: ...


def build_rds_client(region_code: str) -> Any:
    if boto3 is None:
        raise AwsConfigError("boto3 dependency is not installed")
    return boto3.client("rds", region_name=region_code)


def build_elbv2_client(region_code: str) -> Any:
    if boto3 is None:
        raise AwsConfigError("boto3 dependency is not installed")
    return boto3.client("elbv2", region_name=region_code)


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

    def get_target_group_status(
        self,
        region_code: str,
        target_group_name: str,
    ) -> dict[str, object]:
        return {
            "target_group_name": target_group_name,
            "target_group_arn": f"arn:aws:elasticloadbalancing:{region_code}:123:targetgroup/api/abc123",
            "target_type": "ip",
            "protocol": "HTTP",
            "port": 8080,
            "vpc_id": "vpc-12345",
            "healthy_count": 2,
            "unhealthy_count": 0,
            "initial_count": 0,
            "draining_count": 0,
            "unused_count": 0,
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

    def get_target_group_status(
        self,
        region_code: str,
        target_group_name: str,
    ) -> dict[str, object]:
        try:
            client = self._client_factory(region_code)
            groups_response = client.describe_target_groups(Names=[_target_group_short_name(target_group_name)])
        except Exception as error:
            if self._client_error_cls is not None and isinstance(error, self._client_error_cls):
                code = str(getattr(error, "response", {}).get("Error", {}).get("Code") or "")
                if code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation"}:
                    raise AwsAccessDeniedError("aws access denied") from error
                if code in {"TargetGroupNotFound", "TargetGroupNotFoundException"}:
                    raise AwsResourceNotFoundError("target group not found") from error
                raise AwsApiError("failed to describe target group") from error
            if isinstance(error, AwsError):
                raise
            raise AwsApiError("failed to describe target group") from error

        groups = groups_response.get("TargetGroups", [])
        if not groups:
            raise AwsResourceNotFoundError("target group not found")

        group = groups[0]
        target_group_arn = str(group.get("TargetGroupArn") or "")
        try:
            health_response = client.describe_target_health(TargetGroupArn=target_group_arn)
        except Exception as error:
            if self._client_error_cls is not None and isinstance(error, self._client_error_cls):
                code = str(getattr(error, "response", {}).get("Error", {}).get("Code") or "")
                if code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation"}:
                    raise AwsAccessDeniedError("aws access denied") from error
                if code in {"TargetGroupNotFound", "TargetGroupNotFoundException"}:
                    raise AwsResourceNotFoundError("target group not found") from error
                raise AwsApiError("failed to describe target health") from error
            if isinstance(error, AwsError):
                raise
            raise AwsApiError("failed to describe target health") from error

        counts = {
            "healthy_count": 0,
            "unhealthy_count": 0,
            "initial_count": 0,
            "draining_count": 0,
            "unused_count": 0,
        }
        for description in health_response.get("TargetHealthDescriptions", []):
            state = str((description.get("TargetHealth") or {}).get("State") or "").lower()
            if state == "healthy":
                counts["healthy_count"] += 1
            elif state == "unhealthy":
                counts["unhealthy_count"] += 1
            elif state == "initial":
                counts["initial_count"] += 1
            elif state == "draining":
                counts["draining_count"] += 1
            elif state == "unused":
                counts["unused_count"] += 1

        return {
            "target_group_name": target_group_name,
            "target_group_arn": target_group_arn,
            "target_type": str(group.get("TargetType") or "unknown"),
            "protocol": str(group.get("Protocol") or "unknown"),
            "port": group.get("Port"),
            "vpc_id": str(group.get("VpcId") or "unknown"),
            **counts,
        }


def _target_group_short_name(target_group_name: str) -> str:
    parts = target_group_name.split("/")
    if len(parts) >= 2:
        return parts[-2]
    return target_group_name
