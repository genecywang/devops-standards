from alert_auto_investigator.control.pipeline import ControlPipeline
from alert_auto_investigator.models.control_decision import ControlAction
from alert_auto_investigator.models.control_policy import ControlPolicy
from alert_auto_investigator.models.normalized_alert_event import NormalizedAlertEvent


class FakeAlertStateStore:
    def __init__(
        self,
        in_cooldown_keys: frozenset[str] = frozenset(),
        recent_count: int = 0,
    ) -> None:
        self._in_cooldown_keys = in_cooldown_keys
        self._recent_count = recent_count
        self.recorded: list[str] = []

    def was_investigated_within(self, alert_key: str, seconds: float) -> bool:
        return alert_key in self._in_cooldown_keys

    def record_investigation(self, alert_key: str) -> None:
        self.recorded.append(alert_key)

    def count_recent_investigations(self, window_seconds: float) -> int:
        return self._recent_count


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


def make_event(**overrides) -> NormalizedAlertEvent:
    defaults = dict(
        schema_version="v1",
        source="cloudwatch_alarm",
        status="firing",
        environment="prod-jp",
        region_code="ap-northeast-1",
        alert_name="p-rds-shuriken_ReadIOPS",
        alert_key="cloudwatch_alarm:123:ap-northeast-1:p-rds-shuriken_ReadIOPS",
        resource_type="rds_instance",
        resource_name="shuriken",
        summary="CloudWatch alarm triggered",
        event_time="2026-04-12T13:05:43Z",
    )
    defaults.update(overrides)
    return NormalizedAlertEvent(**defaults)


def make_pipeline(policy: ControlPolicy | None = None, store: FakeAlertStateStore | None = None) -> ControlPipeline:
    return ControlPipeline(
        policy=policy or make_policy(),
        store=store or FakeAlertStateStore(),
    )


# --- happy path ---

def test_evaluate_returns_investigate_when_all_checks_pass() -> None:
    pipeline = make_pipeline()
    decision = pipeline.evaluate(make_event())

    assert decision.action == ControlAction.INVESTIGATE
    assert "all checks passed" in decision.reason


# --- fail-close ---

def test_evaluate_skips_when_alert_key_is_empty() -> None:
    decision = make_pipeline().evaluate(make_event(alert_key=""))

    assert decision.action == ControlAction.SKIP
    assert "missing alert_key" in decision.reason


# --- status checks ---

def test_evaluate_skips_resolved_status() -> None:
    decision = make_pipeline().evaluate(make_event(status="resolved"))

    assert decision.action == ControlAction.SKIP
    assert "resolved" in decision.reason


def test_evaluate_skips_unknown_status() -> None:
    decision = make_pipeline().evaluate(make_event(status="unknown"))

    assert decision.action == ControlAction.SKIP
    assert "unknown" in decision.reason


# --- ownership ---

def test_evaluate_skips_when_environment_not_owned() -> None:
    decision = make_pipeline().evaluate(make_event(environment="prod-au"))

    assert decision.action == ControlAction.SKIP
    assert "prod-au" in decision.reason


def test_evaluate_investigates_when_environment_is_owned() -> None:
    policy = make_policy(owned_environments=frozenset({"prod-jp", "prod-au"}))
    decision = make_pipeline(policy=policy).evaluate(make_event(environment="prod-au"))

    assert decision.action == ControlAction.INVESTIGATE


# --- denylist ---

def test_evaluate_skips_when_alert_name_in_denylist() -> None:
    policy = make_policy(investigate_denylist=frozenset({"p-rds-shuriken_ReadIOPS"}))
    decision = make_pipeline(policy=policy).evaluate(make_event())

    assert decision.action == ControlAction.SKIP
    assert "denylist" in decision.reason


def test_evaluate_investigates_when_alert_name_not_in_denylist() -> None:
    policy = make_policy(investigate_denylist=frozenset({"SomeOtherAlert"}))
    decision = make_pipeline(policy=policy).evaluate(make_event())

    assert decision.action == ControlAction.INVESTIGATE


# --- allowlist ---

def test_evaluate_investigates_when_allowlist_is_empty() -> None:
    policy = make_policy(investigate_allowlist=frozenset())
    decision = make_pipeline(policy=policy).evaluate(make_event())

    assert decision.action == ControlAction.INVESTIGATE


def test_evaluate_investigates_when_alert_name_in_allowlist() -> None:
    policy = make_policy(investigate_allowlist=frozenset({"p-rds-shuriken_ReadIOPS", "HostOutOfMemory"}))
    decision = make_pipeline(policy=policy).evaluate(make_event())

    assert decision.action == ControlAction.INVESTIGATE


def test_evaluate_skips_when_allowlist_nonempty_and_alert_name_not_in_it() -> None:
    policy = make_policy(investigate_allowlist=frozenset({"HostOutOfMemory"}))
    decision = make_pipeline(policy=policy).evaluate(make_event())

    assert decision.action == ControlAction.SKIP
    assert "allowlist" in decision.reason


def test_denylist_takes_priority_over_allowlist() -> None:
    policy = make_policy(
        investigate_allowlist=frozenset({"p-rds-shuriken_ReadIOPS"}),
        investigate_denylist=frozenset({"p-rds-shuriken_ReadIOPS"}),
    )
    decision = make_pipeline(policy=policy).evaluate(make_event())

    assert decision.action == ControlAction.SKIP
    assert "denylist" in decision.reason


# --- cooldown ---

def test_evaluate_skips_when_in_cooldown() -> None:
    alert_key = "cloudwatch_alarm:123:ap-northeast-1:p-rds-shuriken_ReadIOPS"
    store = FakeAlertStateStore(in_cooldown_keys=frozenset({alert_key}))
    decision = make_pipeline(store=store).evaluate(make_event())

    assert decision.action == ControlAction.SKIP
    assert "cooldown" in decision.reason


def test_evaluate_investigates_when_different_key_in_cooldown() -> None:
    store = FakeAlertStateStore(in_cooldown_keys=frozenset({"other_alert_key"}))
    decision = make_pipeline(store=store).evaluate(make_event())

    assert decision.action == ControlAction.INVESTIGATE


# --- rate limit ---

def test_evaluate_skips_when_rate_limit_exactly_reached() -> None:
    policy = make_policy(rate_limit_count=5)
    store = FakeAlertStateStore(recent_count=5)
    decision = make_pipeline(policy=policy, store=store).evaluate(make_event())

    assert decision.action == ControlAction.SKIP
    assert "rate limit" in decision.reason


def test_evaluate_investigates_one_below_rate_limit() -> None:
    policy = make_policy(rate_limit_count=5)
    store = FakeAlertStateStore(recent_count=4)
    decision = make_pipeline(policy=policy, store=store).evaluate(make_event())

    assert decision.action == ControlAction.INVESTIGATE


# --- record_investigation ---

def test_record_investigation_delegates_to_store() -> None:
    store = FakeAlertStateStore()
    pipeline = make_pipeline(store=store)
    event = make_event()

    pipeline.record_investigation(event)

    assert store.recorded == [event.alert_key]
