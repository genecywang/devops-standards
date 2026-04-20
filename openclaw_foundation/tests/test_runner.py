from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.tools.aws_elasticache_cluster_status import AwsElastiCacheClusterStatusTool
from openclaw_foundation.tools.kubernetes_pod_status import KubernetesPodStatusTool
from openclaw_foundation.tools.aws_target_group_status import AwsTargetGroupStatusTool
from openclaw_foundation.tools.aws_load_balancer_status import AwsLoadBalancerStatusTool
from openclaw_foundation.tools.aws_rds_instance_status import AwsRdsInstanceStatusTool
from openclaw_foundation.runtime.runner import OpenClawRunner
from openclaw_foundation.runtime.state_machine import RuntimeState
from openclaw_foundation.adapters.aws import AwsAccessDeniedError, FakeAwsProviderAdapter
from openclaw_foundation.adapters.kubernetes import FakeKubernetesProviderAdapter
from openclaw_foundation.tools.fake_investigation import FakeInvestigationTool
from openclaw_foundation.tools.registry import ToolRegistry


def make_request() -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-001",
        source_product="alert_auto_investigator",
        scope={"environment": "staging", "cluster": "staging-main"},
        input_ref="fixture:demo",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=30,
            max_output_tokens=256,
        ),
    )


def test_registry_returns_registered_tool() -> None:
    registry = ToolRegistry()
    tool = FakeInvestigationTool()

    registry.register(tool)

    assert registry.get("fake_investigation") is tool


def test_fake_tool_returns_summary_and_evidence() -> None:
    tool = FakeInvestigationTool()

    result = tool.invoke(make_request())

    assert "req-001" in result.summary
    assert result.evidence == [{"input_ref": "fixture:demo"}]
    assert result.metadata == {"kind": "fake"}


def test_runner_success_path() -> None:
    registry = ToolRegistry()
    registry.register(FakeInvestigationTool())
    runner = OpenClawRunner(registry)

    response = runner.run(make_request())

    assert response.request_id == "req-001"
    assert response.result_state == "success"
    assert response.actions_attempted == ["fake_investigation"]
    assert response.redaction_applied is True
    assert response.metadata == {"kind": "fake"}
    assert runner.state_history == [
        RuntimeState.RECEIVED,
        RuntimeState.VALIDATED,
        RuntimeState.EXECUTING,
        RuntimeState.REDACTING,
        RuntimeState.COMPLETED,
    ]


def test_runner_missing_tool_returns_failed() -> None:
    runner = OpenClawRunner(ToolRegistry())

    response = runner.run(make_request())

    assert response.result_state == "failed"
    assert response.actions_attempted == []


def test_runner_budget_exceeded_returns_fallback() -> None:
    registry = ToolRegistry()
    registry.register(FakeInvestigationTool())
    runner = OpenClawRunner(registry)
    request = make_request()
    request.budget.max_tool_calls = 0

    response = runner.run(request)

    assert response.result_state == "fallback"


def test_runner_executes_kubernetes_pod_status_tool() -> None:
    registry = ToolRegistry()
    registry.register(
        KubernetesPodStatusTool(
            adapter=FakeKubernetesProviderAdapter(),
            allowed_clusters={"staging-main"},
            allowed_namespaces={"dev"},
        )
    )
    runner = OpenClawRunner(registry)
    request = InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-k8s-001",
        source_product="alert_auto_investigator",
        scope={"environment": "staging", "cluster": "staging-main"},
        input_ref="fixture:k8s-demo",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=30,
            max_output_tokens=256,
        ),
        tool_name="get_pod_status",
        target={
            "cluster": "staging-main",
            "namespace": "dev",
            "pod_name": "dev-api-123",
        },
    )

    response = runner.run(request)

    assert response.result_state == "success"
    assert response.actions_attempted == ["get_pod_status"]
    assert "dev-api-123" in response.summary


def test_runner_executes_rds_instance_status_tool() -> None:
    registry = ToolRegistry()
    registry.register(AwsRdsInstanceStatusTool(adapter=FakeAwsProviderAdapter()))
    runner = OpenClawRunner(registry)
    request = InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-rds-001",
        source_product="alert_auto_investigator",
        scope={"environment": "prod-jp", "cluster": "", "region_code": "ap-northeast-1"},
        input_ref="fixture:rds-demo",
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
            "resource_name": "shuriken",
        },
    )

    response = runner.run(request)

    assert response.result_state == "success"
    assert response.actions_attempted == ["get_rds_instance_status"]
    assert "rds instance shuriken is available" in response.summary
    assert response.metadata == {
        "health_state": "healthy",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "available",
    }


def test_runner_executes_elasticache_cluster_status_tool() -> None:
    registry = ToolRegistry()
    registry.register(AwsElastiCacheClusterStatusTool(adapter=FakeAwsProviderAdapter()))
    runner = OpenClawRunner(registry)
    request = InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-elasticache-001",
        source_product="alert_auto_investigator",
        scope={"environment": "prod-jp", "cluster": "", "region_code": "ap-northeast-1"},
        input_ref="fixture:elasticache-demo",
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
            "resource_name": "prod-redis",
        },
    )

    response = runner.run(request)

    assert response.result_state == "success"
    assert response.actions_attempted == ["get_elasticache_cluster_status"]
    assert "elasticache cluster prod-redis is available" in response.summary
    assert response.metadata == {
        "health_state": "healthy",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "available",
    }


def test_runner_returns_successful_canonical_response_when_elasticache_access_is_denied() -> None:
    class AccessDeniedAdapter:
        def get_elasticache_cluster_status(
            self, region_code: str, cache_cluster_id: str
        ) -> dict[str, object]:
            raise AwsAccessDeniedError("aws access denied")

    registry = ToolRegistry()
    registry.register(AwsElastiCacheClusterStatusTool(adapter=AccessDeniedAdapter()))
    runner = OpenClawRunner(registry)
    request = InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-elasticache-denied-001",
        source_product="alert_auto_investigator",
        scope={"environment": "prod-jp", "cluster": "", "region_code": "ap-northeast-1"},
        input_ref="fixture:elasticache-denied-demo",
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
            "resource_name": "prod-redis",
        },
    )

    response = runner.run(request)

    assert response.result_state == "success"
    assert response.actions_attempted == ["get_elasticache_cluster_status"]
    assert response.summary == (
        "elasticache cluster prod-redis could not be inspected in region ap-northeast-1: "
        "aws access denied"
    )
    assert response.metadata == {
        "health_state": "failed",
        "attention_required": True,
        "resource_exists": True,
        "primary_reason": "AccessDenied",
    }


def test_runner_executes_target_group_status_tool() -> None:
    registry = ToolRegistry()
    registry.register(AwsTargetGroupStatusTool(adapter=FakeAwsProviderAdapter()))
    runner = OpenClawRunner(registry)
    request = InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-tg-001",
        source_product="alert_auto_investigator",
        scope={"environment": "prod-jp", "cluster": "", "region_code": "ap-northeast-1"},
        input_ref="fixture:tg-demo",
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
            "resource_name": "targetgroup/api/abc123",
        },
    )

    response = runner.run(request)

    assert response.result_state == "success"
    assert response.actions_attempted == ["get_target_group_status"]
    assert "target group targetgroup/api/abc123 is healthy" in response.summary
    assert response.metadata == {
        "health_state": "healthy",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "HealthyTargets",
    }


def test_runner_executes_load_balancer_status_tool() -> None:
    registry = ToolRegistry()
    registry.register(AwsLoadBalancerStatusTool(adapter=FakeAwsProviderAdapter()))
    runner = OpenClawRunner(registry)
    request = InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-lb-001",
        source_product="alert_auto_investigator",
        scope={"environment": "prod-jp", "cluster": "", "region_code": "ap-northeast-1"},
        input_ref="fixture:lb-demo",
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
            "resource_name": "app/prod-api/abc123",
        },
    )

    response = runner.run(request)

    assert response.result_state == "success"
    assert response.actions_attempted == ["get_load_balancer_status"]
    assert "load balancer app/prod-api/abc123 is active" in response.summary
    assert response.metadata == {
        "health_state": "healthy",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "active",
    }
