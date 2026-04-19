from ast import literal_eval
from dataclasses import dataclass
from pathlib import Path

from alert_auto_investigator.control.pipeline import ControlPipeline
from alert_auto_investigator.control.store import InMemoryAlertStateStore
from alert_auto_investigator.investigation.dispatcher import (
    DEFAULT_TOOL_ROUTING,
    InvestigationConfig,
    OpenClawDispatcher,
)
from alert_auto_investigator.models.control_decision import ControlAction
from alert_auto_investigator.models.control_policy import ControlPolicy
from alert_auto_investigator.normalizers.alertmanager import normalize as normalize_alertmanager
from alert_auto_investigator.normalizers.cloudwatch_alarm import normalize as normalize_cloudwatch_alarm


@dataclass
class FakeResponse:
    request_id: str
    summary: str


class FakeRunner:
    def __init__(self) -> None:
        self.last_request = None

    def run(self, request) -> FakeResponse:
        self.last_request = request
        return FakeResponse(request_id=request.request_id, summary="ok")


def make_policy(**overrides) -> ControlPolicy:
    defaults = dict(
        owned_environments=frozenset({"prod-jp"}),
        investigate_allowlist=frozenset(),
        investigate_denylist=frozenset(),
        cooldown_seconds=900.0,
        rate_limit_count=10,
        rate_limit_window_seconds=3600.0,
    )
    defaults.update(overrides)
    return ControlPolicy(**defaults)


def make_dispatcher() -> tuple[OpenClawDispatcher, FakeRunner]:
    runner = FakeRunner()
    dispatcher = OpenClawDispatcher(
        runner=runner,
        config=InvestigationConfig(
            tool_routing=dict(DEFAULT_TOOL_ROUTING),
            max_steps=3,
            max_tool_calls=2,
            max_duration_seconds=30,
            max_output_tokens=1024,
        ),
    )
    return dispatcher, runner


def load_real_cloudwatch_payload() -> dict:
    path = Path(__file__).resolve().parents[2] / "backlog" / "aws" / "message-output.md"
    content = path.read_text(encoding="utf-8").strip()
    return literal_eval(content)["message_output"]


def make_alertmanager_alert(**overrides) -> dict:
    alert = {
        "status": "firing",
        "startsAt": "2026-04-15T08:00:00Z",
        "endsAt": "2026-04-15T08:05:00Z",
        "labels": {
            "alertname": "HttpBlackboxProbeFailed",
            "cluster": "H2-EKS-DEV-STG",
            "namespace": "backend",
            "severity": "critical",
            "pod": "backend-api-7f6d9",
        },
        "annotations": {
            "summary": "Backend API probe failed",
            "description": "Http Probe down",
        },
    }
    alert.update(overrides)
    return alert


def test_cloudwatch_alarm_firing_is_approved_but_unmapped_for_dispatcher() -> None:
    payload = load_real_cloudwatch_payload()
    payload["NewStateValue"] = "ALARM"

    event = normalize_cloudwatch_alarm(payload, environment="prod-jp")
    pipeline = ControlPipeline(policy=make_policy(), store=InMemoryAlertStateStore())
    decision = pipeline.evaluate(event)
    dispatcher, runner = make_dispatcher()
    response = dispatcher.dispatch(event)

    assert decision.action == ControlAction.INVESTIGATE
    assert event.resource_type == "unknown"
    assert response is None
    assert runner.last_request is None


def test_cloudwatch_alarm_ok_is_skipped_by_control_plane() -> None:
    payload = load_real_cloudwatch_payload()

    event = normalize_cloudwatch_alarm(payload, environment="prod-jp")
    pipeline = ControlPipeline(policy=make_policy(), store=InMemoryAlertStateStore())
    decision = pipeline.evaluate(event)

    assert decision.action == ControlAction.SKIP
    assert "resolved" in decision.reason


def test_cloudwatch_rds_alarm_reaches_dispatcher() -> None:
    payload = {
        "AlarmName": "p-rds-shuriken_ReadIOPS",
        "AWSAccountId": "416885395773",
        "NewStateValue": "ALARM",
        "StateChangeTime": "2026-04-18T01:02:03.000+0000",
        "AlarmArn": "arn:aws:cloudwatch:ap-northeast-1:416885395773:alarm:p-rds-shuriken_ReadIOPS",
        "Trigger": {
            "Dimensions": [
                {
                    "name": "DBInstanceIdentifier",
                    "value": "shuriken",
                }
            ]
        },
    }

    event = normalize_cloudwatch_alarm(payload, environment="prod-jp")
    pipeline = ControlPipeline(policy=make_policy(), store=InMemoryAlertStateStore())
    decision = pipeline.evaluate(event)
    dispatcher, runner = make_dispatcher()
    response = dispatcher.dispatch(event)

    assert decision.action == ControlAction.INVESTIGATE
    assert event.resource_type == "rds_instance"
    assert response is not None
    assert runner.last_request.tool_name == "get_rds_instance_status"


def test_alertmanager_pod_alert_reaches_dispatcher() -> None:
    alert = make_alertmanager_alert()

    event = normalize_alertmanager(alert, environment="prod-jp", region_code="ap-northeast-1")
    pipeline = ControlPipeline(policy=make_policy(), store=InMemoryAlertStateStore())
    decision = pipeline.evaluate(event)
    dispatcher, runner = make_dispatcher()
    response = dispatcher.dispatch(event)

    assert decision.action == ControlAction.INVESTIGATE
    assert response is not None
    assert runner.last_request.tool_name == "get_pod_events"


def test_alertmanager_resolved_alert_is_skipped() -> None:
    alert = make_alertmanager_alert(status="resolved")

    event = normalize_alertmanager(alert, environment="prod-jp", region_code="ap-northeast-1")
    pipeline = ControlPipeline(policy=make_policy(), store=InMemoryAlertStateStore())
    decision = pipeline.evaluate(event)

    assert decision.action == ControlAction.SKIP
    assert "resolved" in decision.reason


def test_cooldown_prevents_duplicate_investigation() -> None:
    event = normalize_alertmanager(
        make_alertmanager_alert(),
        environment="prod-jp",
        region_code="ap-northeast-1",
    )
    store = InMemoryAlertStateStore()
    pipeline = ControlPipeline(policy=make_policy(), store=store)

    first = pipeline.evaluate(event)
    pipeline.record_investigation(event)
    second = pipeline.evaluate(event)

    assert first.action == ControlAction.INVESTIGATE
    assert second.action == ControlAction.SKIP
    assert "cooldown" in second.reason


def test_rate_limit_blocks_when_exceeded() -> None:
    store = InMemoryAlertStateStore()
    policy = make_policy(rate_limit_count=2)
    pipeline = ControlPipeline(policy=policy, store=store)
    first_event = normalize_alertmanager(
        make_alertmanager_alert(),
        environment="prod-jp",
        region_code="ap-northeast-1",
    )
    second_event = normalize_alertmanager(
        make_alertmanager_alert(labels={
            "alertname": "HttpBlackboxProbeFailed",
            "cluster": "H2-EKS-DEV-STG",
            "namespace": "backend",
            "severity": "critical",
            "pod": "backend-api-8d19a",
        }),
        environment="prod-jp",
        region_code="ap-northeast-1",
    )
    third_event = normalize_alertmanager(
        make_alertmanager_alert(labels={
            "alertname": "HttpBlackboxProbeFailed",
            "cluster": "H2-EKS-DEV-STG",
            "namespace": "backend",
            "severity": "critical",
            "pod": "backend-api-9a55b",
        }),
        environment="prod-jp",
        region_code="ap-northeast-1",
    )

    assert pipeline.evaluate(first_event).action == ControlAction.INVESTIGATE
    pipeline.record_investigation(first_event)
    assert pipeline.evaluate(second_event).action == ControlAction.INVESTIGATE
    pipeline.record_investigation(second_event)

    third_decision = pipeline.evaluate(third_event)

    assert third_decision.action == ControlAction.SKIP
    assert "rate limit" in third_decision.reason
