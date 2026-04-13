import os

from self_service_copilot.config import CopilotConfig


def test_from_env_parses_allowed_channel_ids(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "payments")
    monkeypatch.setenv("COPILOT_ALLOWED_CHANNEL_IDS", "C123, C456")
    monkeypatch.setenv("COPILOT_PROVIDER", "fake")

    config = CopilotConfig.from_env()

    assert config.allowed_channel_ids == {"C123", "C456"}


def test_from_env_includes_get_deployment_status_in_supported_tools(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "payments")
    monkeypatch.delenv("COPILOT_ALLOWED_CHANNEL_IDS", raising=False)
    monkeypatch.setenv("COPILOT_PROVIDER", "fake")

    config = CopilotConfig.from_env()

    assert "get_deployment_status" in config.supported_tools


def test_from_env_includes_get_pod_runtime_in_supported_tools(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "payments")
    monkeypatch.delenv("COPILOT_ALLOWED_CHANNEL_IDS", raising=False)
    monkeypatch.setenv("COPILOT_PROVIDER", "fake")

    config = CopilotConfig.from_env()

    assert "get_pod_runtime" in config.supported_tools


def test_from_env_includes_get_deployment_restart_rate_in_supported_tools(
    monkeypatch,
) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "payments")
    monkeypatch.delenv("COPILOT_ALLOWED_CHANNEL_IDS", raising=False)
    monkeypatch.setenv("COPILOT_PROVIDER", "fake")

    config = CopilotConfig.from_env()

    assert "get_deployment_restart_rate" in config.supported_tools


def test_from_env_reads_prometheus_base_url(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "payments")
    monkeypatch.setenv("OPENCLAW_PROMETHEUS_BASE_URL", "http://prometheus.monitoring.svc:9090")
    monkeypatch.delenv("COPILOT_ALLOWED_CHANNEL_IDS", raising=False)
    monkeypatch.setenv("COPILOT_PROVIDER", "real")

    config = CopilotConfig.from_env()

    assert config.prometheus_base_url == "http://prometheus.monitoring.svc:9090"


def test_from_env_uses_default_rate_limits(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "payments")
    monkeypatch.setenv("COPILOT_PROVIDER", "fake")
    monkeypatch.delenv("COPILOT_ALLOWED_CHANNEL_IDS", raising=False)
    monkeypatch.delenv("COPILOT_USER_RATE_LIMIT_COUNT", raising=False)
    monkeypatch.delenv("COPILOT_USER_RATE_LIMIT_WINDOW_SECONDS", raising=False)
    monkeypatch.delenv("COPILOT_CHANNEL_RATE_LIMIT_COUNT", raising=False)
    monkeypatch.delenv("COPILOT_CHANNEL_RATE_LIMIT_WINDOW_SECONDS", raising=False)

    config = CopilotConfig.from_env()

    assert config.user_rate_limit_count == 5
    assert config.user_rate_limit_window_seconds == 60
    assert config.channel_rate_limit_count == 20
    assert config.channel_rate_limit_window_seconds == 60


def test_from_env_reads_rate_limit_overrides(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "payments")
    monkeypatch.setenv("COPILOT_PROVIDER", "fake")
    monkeypatch.delenv("COPILOT_ALLOWED_CHANNEL_IDS", raising=False)
    monkeypatch.setenv("COPILOT_USER_RATE_LIMIT_COUNT", "7")
    monkeypatch.setenv("COPILOT_USER_RATE_LIMIT_WINDOW_SECONDS", "30")
    monkeypatch.setenv("COPILOT_CHANNEL_RATE_LIMIT_COUNT", "50")
    monkeypatch.setenv("COPILOT_CHANNEL_RATE_LIMIT_WINDOW_SECONDS", "120")

    config = CopilotConfig.from_env()

    assert config.user_rate_limit_count == 7
    assert config.user_rate_limit_window_seconds == 30
    assert config.channel_rate_limit_count == 50
    assert config.channel_rate_limit_window_seconds == 120
