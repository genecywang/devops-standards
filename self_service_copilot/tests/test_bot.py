import logging
from types import SimpleNamespace

from openclaw_foundation.adapters.kubernetes import KubernetesResourceNotFoundError
from openclaw_foundation.adapters.prometheus import PrometheusQueryError
from openclaw_foundation.models.enums import ResultState
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


class SuccessRunner:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def run(self, request):
        self.calls.append(request)
        return SimpleNamespace(
            result_state=ResultState.SUCCESS,
            summary="pod payments-api-123 is Running",
        )


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


def test_build_registry_registers_get_pod_cpu_usage_tool() -> None:
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
                "get_pod_cpu_usage",
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

    tool = registry.get("get_pod_cpu_usage")
    assert tool.tool_name == "get_pod_cpu_usage"


def test_build_registry_registers_get_deployment_restart_rate_tool() -> None:
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
                "get_deployment_restart_rate",
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
        user_rate_limit_count=5,
        user_rate_limit_window_seconds=60,
        channel_rate_limit_count=20,
        channel_rate_limit_window_seconds=60,
    )

    registry = build_registry(config)

    tool = registry.get("get_deployment_restart_rate")
    assert tool.tool_name == "get_deployment_restart_rate"


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


def test_handle_mention_event_logs_dispatch_denial_metadata(caplog) -> None:
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
        user_rule=RateLimitRule(limit=10, window_seconds=60),
        channel_rule=RateLimitRule(limit=10, window_seconds=60),
    )
    event = {
        "channel": "C1",
        "user": "U1",
        "text": "<@UBOT> staging get_pod_status payments payments-api-123;",
        "ts": "1710000000.000100",
    }

    with caplog.at_level(logging.INFO):
        handle_mention_event(
            event=event,
            say=say,
            config=config,
            bot_user_id="UBOT",
            runner=runner,
            limiter=limiter,
        )

    assert "[denied]" in say.calls[0][0]
    assert "dispatch denied" in caplog.text
    assert "tool=get_pod_status" in caplog.text
    assert "namespace=payments" in caplog.text
    assert "resource_name=payments-api-123;" in caplog.text


def test_handle_mention_event_ignores_manual_command_for_other_environment() -> None:
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
        user_rule=RateLimitRule(limit=10, window_seconds=60),
        channel_rule=RateLimitRule(limit=10, window_seconds=60),
    )
    event = {
        "channel": "C1",
        "user": "U1",
        "text": "<@UBOT> prod get_pod_status payments payments-api-123",
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

    assert say.calls == []
    assert runner.calls == []


def test_handle_mention_event_ignores_prometheus_alert_for_other_cluster() -> None:
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
        user_rule=RateLimitRule(limit=10, window_seconds=60),
        channel_rule=RateLimitRule(limit=10, window_seconds=60),
    )
    event = {
        "channel": "C1",
        "user": "U1",
        "text": "AlertSource: prometheus\nCluster: prod-main\nSeverity: warning",
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

    assert say.calls == []
    assert runner.calls == []


def test_handle_mention_event_logs_ownership_decision_for_ignored_path(caplog) -> None:
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
        user_rule=RateLimitRule(limit=10, window_seconds=60),
        channel_rule=RateLimitRule(limit=10, window_seconds=60),
    )
    event = {
        "channel": "C1",
        "user": "U1",
        "text": "<@UBOT> prod get_pod_status payments payments-api-123",
        "ts": "1710000000.000100",
    }

    with caplog.at_level(logging.INFO):
        handle_mention_event(
            event=event,
            say=say,
            config=config,
            bot_user_id="UBOT",
            runner=runner,
            limiter=limiter,
        )

    assert "ownership decision" in caplog.text
    assert "source_type=manual_command" in caplog.text
    assert "target_environment=prod" in caplog.text
    assert "target_cluster=None" in caplog.text
    assert "my_environment=staging" in caplog.text
    assert "my_cluster=staging-main" in caplog.text
    assert "decision=ignored" in caplog.text
    assert "reason=not_my_environment" in caplog.text


def test_handle_mention_event_matching_prometheus_alert_is_filtered_without_reply() -> None:
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
        user_rule=RateLimitRule(limit=10, window_seconds=60),
        channel_rule=RateLimitRule(limit=10, window_seconds=60),
    )
    event = {
        "channel": "C1",
        "user": "U1",
        "text": "AlertSource: prometheus\nCluster: staging-main\nSeverity: warning",
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

    assert say.calls == []
    assert runner.calls == []


def test_handle_mention_event_preserves_parse_error_reply_for_malformed_manual_command() -> None:
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
        user_rule=RateLimitRule(limit=10, window_seconds=60),
        channel_rule=RateLimitRule(limit=10, window_seconds=60),
    )
    event = {
        "channel": "C1",
        "user": "U1",
        "text": "<@UBOT> get_pod_status payments",
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

    assert len(say.calls) == 1
    assert say.calls[0][0].startswith("[usage]")
    assert runner.calls == []


def test_handle_mention_event_preserves_three_token_manual_command_path() -> None:
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
    runner = SuccessRunner()
    limiter = CopilotRateLimiter(
        user_rule=RateLimitRule(limit=10, window_seconds=60),
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

    assert len(runner.calls) == 1
    assert len(say.calls) == 1
    assert say.calls[0][0].startswith("[success] get_pod_status payments/payments-api-123")
