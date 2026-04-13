import logging

from openclaw_foundation.adapters.kubernetes import KubernetesResourceNotFoundError
from openclaw_foundation.adapters.prometheus import PrometheusQueryError
from openclaw_foundation.models.requests import ExecutionBudget

from self_service_copilot.bot import (
    build_registry,
    handle_mention_event,
    is_expected_platform_error,
    should_handle_channel,
)
from self_service_copilot.config import CopilotConfig
from self_service_copilot.rate_limit import CopilotRateLimiter, RateLimitRule


class RecordingSay:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, message: str, thread_ts: str) -> None:
        self.calls.append((message, thread_ts))


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def run(self, request):
        self.calls.append(request)
        raise AssertionError("runner should not be called")


def test_should_handle_channel_returns_false_for_disallowed_channel() -> None:
    assert should_handle_channel("C999", {"C123", "C456"}) is False


def test_should_handle_channel_returns_true_for_allowed_channel() -> None:
    assert should_handle_channel("C123", {"C123", "C456"}) is True


def test_should_handle_channel_returns_true_when_allowlist_is_empty() -> None:
    assert should_handle_channel("C999", set()) is True


def test_build_registry_registers_get_deployment_status_tool() -> None:
    config = CopilotConfig(
        cluster="staging-main",
        environment="staging",
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
        prometheus_base_url=None,
        supported_tools=frozenset(
            {"get_pod_status", "get_pod_events", "get_deployment_status"}
        ),
        default_budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=15,
            max_output_tokens=512,
        ),
        provider="fake",
        allowed_channel_ids=set(),
    )

    registry = build_registry(config)

    tool = registry.get("get_deployment_status")
    assert tool.tool_name == "get_deployment_status"


def test_build_registry_registers_get_pod_runtime_tool() -> None:
    config = CopilotConfig(
        cluster="staging-main",
        environment="staging",
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
        prometheus_base_url=None,
        supported_tools=frozenset(
            {
                "get_pod_status",
                "get_pod_events",
                "get_deployment_status",
                "get_pod_runtime",
            }
        ),
        default_budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=15,
            max_output_tokens=512,
        ),
        provider="fake",
        allowed_channel_ids=set(),
    )

    registry = build_registry(config)

    tool = registry.get("get_pod_runtime")
    assert tool.tool_name == "get_pod_runtime"


def test_is_expected_platform_error_returns_true_for_prometheus_error() -> None:
    assert is_expected_platform_error(PrometheusQueryError("no metrics found for pod")) is True


def test_is_expected_platform_error_returns_true_for_kubernetes_error() -> None:
    assert is_expected_platform_error(KubernetesResourceNotFoundError("pod not found")) is True


def test_is_expected_platform_error_returns_false_for_unexpected_error() -> None:
    assert is_expected_platform_error(RuntimeError("boom")) is False


def test_log_level_from_env_defaults_to_info(monkeypatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    from self_service_copilot.bot import _log_level_from_env
    assert _log_level_from_env() == logging.INFO


def test_log_level_from_env_reads_debug(monkeypatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    from self_service_copilot.bot import _log_level_from_env
    assert _log_level_from_env() == logging.DEBUG


def test_log_level_from_env_falls_back_to_info_for_invalid(monkeypatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "NOTAVALIDLEVEL")
    from self_service_copilot.bot import _log_level_from_env
    assert _log_level_from_env() == logging.INFO


def test_handle_mention_event_replies_when_rate_limited() -> None:
    config = CopilotConfig(
        cluster="staging-main",
        environment="staging",
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
        prometheus_base_url=None,
        supported_tools=frozenset({"get_pod_status"}),
        default_budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=15,
            max_output_tokens=512,
        ),
        provider="fake",
        allowed_channel_ids=set(),
    )
    say = RecordingSay()
    runner = RecordingRunner()
    limiter = CopilotRateLimiter(
        user_rule=RateLimitRule(limit=0, window_seconds=60),
        channel_rule=RateLimitRule(limit=10, window_seconds=60),
    )
    event = {
        "channel": "C1",
        "user": "U1",
        "text": "<@UBOT> get_pod_status payments payments-api-123",
        "ts": "1710000000.000100",
    }

    handle_mention_event(
        event=event,
        say=say,
        config=config,
        bot_user_id="UBOT",
        runner=runner,
        limiter=limiter,
    )

    assert say.calls == [("[denied] rate limit exceeded, please retry later", "1710000000.000100")]


def test_handle_mention_event_rate_limit_blocks_before_runner() -> None:
    config = CopilotConfig(
        cluster="staging-main",
        environment="staging",
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
        prometheus_base_url=None,
        supported_tools=frozenset({"get_pod_status"}),
        default_budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=15,
            max_output_tokens=512,
        ),
        provider="fake",
        allowed_channel_ids=set(),
    )
    say = RecordingSay()
    runner = RecordingRunner()
    limiter = CopilotRateLimiter(
        user_rule=RateLimitRule(limit=0, window_seconds=60),
        channel_rule=RateLimitRule(limit=10, window_seconds=60),
    )
    event = {
        "channel": "C1",
        "user": "U1",
        "text": "<@UBOT> get_pod_status payments payments-api-123",
        "ts": "1710000000.000100",
    }

    handle_mention_event(
        event=event,
        say=say,
        config=config,
        bot_user_id="UBOT",
        runner=runner,
        limiter=limiter,
    )

    assert runner.calls == []
