from dataclasses import dataclass

from alert_auto_investigator.investigation.dispatcher import (
    DEFAULT_TOOL_ROUTING,
    InvestigationConfig,
    OpenClawDispatcher,
)
from alert_auto_investigator.models.normalized_alert_event import NormalizedAlertEvent


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class FakeResponse:
    request_id: str
    summary: str


@dataclass
class FakeRequest:
    request_id: str
    tool_name: str
    target: dict
    scope: dict
    input_ref: str
    source_product: str
    budget: object


class FakeRunner:
    def __init__(self) -> None:
        self.last_request: FakeRequest | None = None

    def run(self, request) -> FakeResponse:
        self.last_request = request
        return FakeResponse(request_id=request.request_id, summary="ok")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_event(**overrides) -> NormalizedAlertEvent:
    defaults = dict(
        schema_version="v1",
        source="alertmanager",
        status="firing",
        environment="prod-jp",
        region_code="ap-northeast-1",
        alert_name="PodCrashLoopBackOff",
        alert_key="alertmanager:staging-main:dev:PodCrashLoopBackOff:dev-api-123",
        resource_type="pod",
        resource_name="dev-api-123",
        summary="Pod is crash looping",
        event_time="2026-04-12T13:00:00Z",
        cluster="staging-main",
        namespace="dev",
    )
    defaults.update(overrides)
    return NormalizedAlertEvent(**defaults)


def make_config(**overrides) -> InvestigationConfig:
    defaults = dict(
        tool_routing=dict(DEFAULT_TOOL_ROUTING),
        max_steps=3,
        max_tool_calls=2,
        max_duration_seconds=30,
        max_output_tokens=1024,
    )
    defaults.update(overrides)
    return InvestigationConfig(**defaults)


def make_dispatcher(config: InvestigationConfig | None = None) -> tuple[OpenClawDispatcher, FakeRunner]:
    runner = FakeRunner()
    dispatcher = OpenClawDispatcher(runner=runner, config=config or make_config())
    return dispatcher, runner


# ---------------------------------------------------------------------------
# Tests: routing
# ---------------------------------------------------------------------------


def test_dispatch_returns_none_for_unmapped_resource_type() -> None:
    dispatcher, runner = make_dispatcher(make_config(tool_routing={}))
    result = dispatcher.dispatch(make_event(resource_type="rds_instance"))

    assert result is None
    assert runner.last_request is None


def test_dispatch_returns_none_for_unknown_resource_type() -> None:
    dispatcher, runner = make_dispatcher()
    result = dispatcher.dispatch(make_event(resource_type="unknown"))

    assert result is None


def test_dispatch_returns_runner_response_for_pod_resource_type() -> None:
    dispatcher, _ = make_dispatcher()
    result = dispatcher.dispatch(make_event(resource_type="pod"))

    assert result is not None


def test_dispatch_routes_pod_to_get_pod_events() -> None:
    dispatcher, runner = make_dispatcher()
    dispatcher.dispatch(make_event(resource_type="pod"))

    assert runner.last_request.tool_name == "get_pod_events"


def test_dispatch_routes_deployment_to_get_deployment_status() -> None:
    dispatcher, runner = make_dispatcher()
    dispatcher.dispatch(make_event(resource_type="deployment"))

    assert runner.last_request.tool_name == "get_deployment_status"


def test_dispatch_routes_job_to_get_job_status() -> None:
    dispatcher, runner = make_dispatcher()
    dispatcher.dispatch(make_event(resource_type="job", resource_name="nightly-backfill-12345"))

    assert runner.last_request.tool_name == "get_job_status"


def test_dispatch_routes_cronjob_to_get_cronjob_status() -> None:
    dispatcher, runner = make_dispatcher()
    dispatcher.dispatch(make_event(resource_type="cronjob", resource_name="nightly-backfill"))

    assert runner.last_request.tool_name == "get_cronjob_status"


def test_dispatch_routes_rds_instance_to_get_rds_instance_status() -> None:
    dispatcher, runner = make_dispatcher()
    dispatcher.dispatch(
        make_event(
            source="cloudwatch_alarm",
            cluster="",
            namespace="",
            resource_type="rds_instance",
            resource_name="shuriken",
        )
    )

    assert runner.last_request.tool_name == "get_rds_instance_status"


def test_dispatch_routes_target_group_to_get_target_group_status() -> None:
    dispatcher, runner = make_dispatcher()
    dispatcher.dispatch(
        make_event(
            source="cloudwatch_alarm",
            cluster="",
            namespace="",
            resource_type="target_group",
            resource_name="targetgroup/api/abc123",
        )
    )

    assert runner.last_request.tool_name == "get_target_group_status"


def test_dispatch_routes_elasticache_cluster_to_get_elasticache_cluster_status() -> None:
    dispatcher, runner = make_dispatcher()
    dispatcher.dispatch(
        make_event(
            source="cloudwatch_alarm",
            cluster="",
            namespace="",
            resource_type="elasticache_cluster",
            resource_name="redis-prod",
        )
    )

    assert runner.last_request.tool_name == "get_elasticache_cluster_status"


def test_dispatch_routes_load_balancer_to_get_load_balancer_status() -> None:
    dispatcher, runner = make_dispatcher()
    dispatcher.dispatch(
        make_event(
            source="cloudwatch_alarm",
            cluster="",
            namespace="",
            resource_type="load_balancer",
            resource_name="app/prod-api/abc123",
        )
    )

    assert runner.last_request.tool_name == "get_load_balancer_status"


def test_dispatch_logs_supported_but_unrouted_for_investigate_type(caplog) -> None:
    dispatcher, runner = make_dispatcher(make_config(tool_routing={}))

    with caplog.at_level("WARNING"):
        result = dispatcher.dispatch(make_event(resource_type="job", resource_name="nightly-backfill-12345"))

    assert result is None
    assert runner.last_request is None
    assert "dispatch_skipped_no_tool resource_type=job policy=supported_but_unrouted" in caplog.text


def test_dispatch_returns_none_for_node_resource_type_by_default() -> None:
    dispatcher, runner = make_dispatcher()
    result = dispatcher.dispatch(make_event(resource_type="node", namespace=""))

    assert result is None
    assert runner.last_request is None


def test_dispatch_honours_custom_tool_routing() -> None:
    config = make_config(tool_routing={"rds_instance": "get_pod_status"})
    dispatcher, runner = make_dispatcher(config)
    dispatcher.dispatch(make_event(resource_type="rds_instance"))

    assert runner.last_request.tool_name == "get_pod_status"


# ---------------------------------------------------------------------------
# Tests: target and scope
# ---------------------------------------------------------------------------


def test_dispatch_builds_target_from_event() -> None:
    dispatcher, runner = make_dispatcher()
    event = make_event(cluster="staging-main", namespace="dev", resource_name="dev-api-123")
    dispatcher.dispatch(event)

    assert runner.last_request.target == {
        "cluster": "staging-main",
        "namespace": "dev",
        "resource_name": "dev-api-123",
    }


def test_dispatch_builds_scope_from_event() -> None:
    dispatcher, runner = make_dispatcher()
    event = make_event(environment="prod-jp", cluster="staging-main", region_code="ap-northeast-1")
    dispatcher.dispatch(event)

    assert runner.last_request.scope == {
        "environment": "prod-jp",
        "cluster": "staging-main",
        "region_code": "ap-northeast-1",
    }


def test_dispatch_sets_input_ref_from_alert_key() -> None:
    dispatcher, runner = make_dispatcher()
    event = make_event()
    dispatcher.dispatch(event)

    assert runner.last_request.input_ref == f"alert:{event.alert_key}"


def test_dispatch_sets_source_product() -> None:
    dispatcher, runner = make_dispatcher()
    dispatcher.dispatch(make_event())

    assert runner.last_request.source_product == "alert_auto_investigator"


# ---------------------------------------------------------------------------
# Tests: request_id
# ---------------------------------------------------------------------------


def test_dispatch_uses_provided_request_id() -> None:
    dispatcher, runner = make_dispatcher()
    dispatcher.dispatch(make_event(), request_id="fixed-id-001")

    assert runner.last_request.request_id == "fixed-id-001"


def test_dispatch_generates_unique_request_id_when_none_provided() -> None:
    dispatcher, runner = make_dispatcher()

    dispatcher.dispatch(make_event())
    id_1 = runner.last_request.request_id

    dispatcher.dispatch(make_event())
    id_2 = runner.last_request.request_id

    assert id_1 != id_2
    assert len(id_1) > 0
    assert len(id_2) > 0


# ---------------------------------------------------------------------------
# Tests: budget
# ---------------------------------------------------------------------------


def test_dispatch_passes_budget_config_to_runner() -> None:
    config = make_config(max_steps=5, max_tool_calls=3, max_duration_seconds=60, max_output_tokens=2048)
    dispatcher, runner = make_dispatcher(config)
    dispatcher.dispatch(make_event())

    budget = runner.last_request.budget
    assert budget.max_steps == 5
    assert budget.max_tool_calls == 3
    assert budget.max_duration_seconds == 60
    assert budget.max_output_tokens == 2048


def test_dispatch_logs_successful_dispatch(caplog) -> None:
    dispatcher, _ = make_dispatcher()

    with caplog.at_level("INFO"):
        dispatcher.dispatch(make_event(resource_type="job", resource_name="nightly-backfill-12345"))

    assert "dispatch_started resource_type=job tool_name=get_job_status" in caplog.text
