from alert_auto_investigator.config import InvestigatorConfig
from alert_auto_investigator.service.runner_factory import build_registry, build_runner
from alert_auto_investigator.service.stub_runner import StubInvestigationRunner
from openclaw_foundation.runtime.runner import OpenClawRunner


def make_config(**overrides) -> InvestigatorConfig:
    defaults = dict(
        slack_bot_token="xoxb-test",
        slack_app_token="xapp-test",
        region_code="ap-east-1",
        fallback_environment="dev",
        owned_environments=["dev"],
        cooldown_seconds=300.0,
        rate_limit_count=10,
        rate_limit_window_seconds=3600.0,
        investigate_allowlist=[],
        investigate_denylist=[],
        provider="stub",
        allowed_clusters=["dev-cluster"],
        allowed_namespaces=["default"],
        prometheus_base_url=None,
    )
    defaults.update(overrides)
    return InvestigatorConfig(**defaults)


def test_build_runner_returns_stub_runner_when_provider_is_stub() -> None:
    runner = build_runner(make_config(provider="stub"))

    assert isinstance(runner, StubInvestigationRunner)


def test_build_runner_returns_openclaw_runner_when_provider_is_real() -> None:
    runner = build_runner(
        make_config(
            provider="real",
            prometheus_base_url="http://prometheus.monitoring:9090",
        )
    )

    assert isinstance(runner, OpenClawRunner)


def test_build_runner_rejects_unknown_provider() -> None:
    try:
        build_runner(make_config(provider="nope"))
    except ValueError as error:
        assert "Unsupported INVESTIGATION_PROVIDER" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_build_registry_requires_prometheus_url_for_real_provider() -> None:
    try:
        build_registry(make_config(provider="real", prometheus_base_url=None))
    except ValueError as error:
        assert "OPENCLAW_PROMETHEUS_BASE_URL is required" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_build_registry_registers_expected_tools() -> None:
    registry = build_registry(make_config(provider="stub"))

    assert registry.get("get_pod_status").tool_name == "get_pod_status"
    assert registry.get("get_pod_events").tool_name == "get_pod_events"
    assert registry.get("get_deployment_status").tool_name == "get_deployment_status"
