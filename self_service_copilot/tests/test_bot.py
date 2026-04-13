import logging

from openclaw_foundation.adapters.kubernetes import KubernetesResourceNotFoundError
from openclaw_foundation.adapters.prometheus import PrometheusQueryError
from openclaw_foundation.models.requests import ExecutionBudget

from self_service_copilot.bot import (
    build_registry,
    is_expected_platform_error,
    should_handle_channel,
)
from self_service_copilot.config import CopilotConfig


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


def test_log_level_from_env_defaults_to_info(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    from importlib import reload
    import self_service_copilot.bot as bot_module
    reload(bot_module)
    assert bot_module._log_level_from_env() == logging.INFO


def test_log_level_from_env_reads_debug(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    from importlib import reload
    import self_service_copilot.bot as bot_module
    reload(bot_module)
    assert bot_module._log_level_from_env() == logging.DEBUG


def test_log_level_from_env_falls_back_to_info_for_invalid(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "NOTAVALIDLEVEL")
    from importlib import reload
    import self_service_copilot.bot as bot_module
    reload(bot_module)
    assert bot_module._log_level_from_env() == logging.INFO
