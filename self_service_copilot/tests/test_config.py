import pytest
from openclaw_foundation.models.requests import ExecutionBudget

from self_service_copilot.config import CopilotConfig


def test_from_env_parses_allowed_channel_ids(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "dev")
    monkeypatch.setenv("COPILOT_ALLOWED_CHANNEL_IDS", "C123, C456")
    monkeypatch.setenv("COPILOT_PROVIDER", "fake")

    config = CopilotConfig.from_env()

    assert config.allowed_channel_ids == {"C123", "C456"}


def test_from_env_uses_cluster_and_environment_as_bot_identity(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "prod-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "production")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "prod-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "dev")
    monkeypatch.setenv("COPILOT_PROVIDER", "fake")
    monkeypatch.delenv("COPILOT_ALLOWED_CHANNEL_IDS", raising=False)

    config = CopilotConfig.from_env()

    assert config.cluster == "prod-main"
    assert config.environment == "production"


def test_copilot_config_positional_constructor_remains_compatible() -> None:
    config = CopilotConfig(
        "staging-main",
        "staging",
        {"staging-main"},
        {"dev"},
        frozenset({"get_pod_status"}),
        ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=15,
            max_output_tokens=512,
        ),
        "fake",
    )

    assert config.cluster == "staging-main"
    assert config.environment == "staging"
    assert config.default_environment == "staging"
    assert config.environment_clusters == {"staging": "staging-main"}


def test_from_env_defaults_environment_mapping_from_legacy_vars(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "dev")
    monkeypatch.setenv("COPILOT_PROVIDER", "fake")
    monkeypatch.delenv("COPILOT_ALLOWED_CHANNEL_IDS", raising=False)
    monkeypatch.delenv("COPILOT_DEFAULT_ENVIRONMENT", raising=False)
    monkeypatch.delenv("COPILOT_ENVIRONMENT_CLUSTERS", raising=False)

    config = CopilotConfig.from_env()

    assert config.default_environment == "staging"
    assert config.environment_clusters == {"staging": "staging-main"}


def test_from_env_reads_environment_cluster_mapping(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_DEFAULT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ENVIRONMENT_CLUSTERS", "staging=staging-main,au=au-main,jp=jp-main")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main,au-main,jp-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "dev")
    monkeypatch.setenv("COPILOT_PROVIDER", "fake")
    monkeypatch.delenv("COPILOT_ALLOWED_CHANNEL_IDS", raising=False)

    config = CopilotConfig.from_env()

    assert config.default_environment == "staging"
    assert config.environment_clusters == {
        "staging": "staging-main",
        "au": "au-main",
        "jp": "jp-main",
    }


def test_from_env_ignores_empty_default_environment(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_DEFAULT_ENVIRONMENT", "")
    monkeypatch.delenv("COPILOT_ENVIRONMENT_CLUSTERS", raising=False)
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "dev")
    monkeypatch.setenv("COPILOT_PROVIDER", "fake")
    monkeypatch.delenv("COPILOT_ALLOWED_CHANNEL_IDS", raising=False)

    config = CopilotConfig.from_env()

    assert config.default_environment == "staging"
    assert config.environment_clusters == {"staging": "staging-main"}


def test_from_env_falls_back_to_default_environment_when_mapping_missing_it(
    monkeypatch,
) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_DEFAULT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ENVIRONMENT_CLUSTERS", "au=au-main,jp=jp-main")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main,au-main,jp-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "dev")
    monkeypatch.setenv("COPILOT_PROVIDER", "fake")
    monkeypatch.delenv("COPILOT_ALLOWED_CHANNEL_IDS", raising=False)

    config = CopilotConfig.from_env()

    assert config.environment_clusters == {
        "au": "au-main",
        "jp": "jp-main",
        "staging": "staging-main",
    }


def test_from_env_falls_back_to_default_environment_for_whitespace_mapping(
    monkeypatch,
) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_DEFAULT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ENVIRONMENT_CLUSTERS", "   ,  ")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "dev")
    monkeypatch.setenv("COPILOT_PROVIDER", "fake")
    monkeypatch.delenv("COPILOT_ALLOWED_CHANNEL_IDS", raising=False)

    config = CopilotConfig.from_env()

    assert config.environment_clusters == {"staging": "staging-main"}


@pytest.mark.parametrize("environment_clusters", ["jp=", "=jp-main"])
def test_from_env_rejects_malformed_environment_cluster_mapping(
    monkeypatch,
    environment_clusters: str,
) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_DEFAULT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ENVIRONMENT_CLUSTERS", environment_clusters)
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "dev")
    monkeypatch.setenv("COPILOT_PROVIDER", "fake")
    monkeypatch.delenv("COPILOT_ALLOWED_CHANNEL_IDS", raising=False)

    with pytest.raises(ValueError, match="COPILOT_ENVIRONMENT_CLUSTERS"):
        CopilotConfig.from_env()


def test_from_env_includes_get_deployment_status_in_supported_tools(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "dev")
    monkeypatch.delenv("COPILOT_ALLOWED_CHANNEL_IDS", raising=False)
    monkeypatch.setenv("COPILOT_PROVIDER", "fake")

    config = CopilotConfig.from_env()

    assert "get_deployment_status" in config.supported_tools


def test_from_env_includes_get_pod_runtime_in_supported_tools(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "dev")
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
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "dev")
    monkeypatch.delenv("COPILOT_ALLOWED_CHANNEL_IDS", raising=False)
    monkeypatch.setenv("COPILOT_PROVIDER", "fake")

    config = CopilotConfig.from_env()

    assert "get_deployment_restart_rate" in config.supported_tools


def test_from_env_includes_get_pod_cpu_usage_in_supported_tools(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "dev")
    monkeypatch.delenv("COPILOT_ALLOWED_CHANNEL_IDS", raising=False)
    monkeypatch.setenv("COPILOT_PROVIDER", "fake")

    config = CopilotConfig.from_env()

    assert "get_pod_cpu_usage" in config.supported_tools


def test_from_env_reads_prometheus_base_url(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "dev")
    monkeypatch.setenv("OPENCLAW_PROMETHEUS_BASE_URL", "http://prometheus.monitoring.svc:9090")
    monkeypatch.delenv("COPILOT_ALLOWED_CHANNEL_IDS", raising=False)
    monkeypatch.setenv("COPILOT_PROVIDER", "real")

    config = CopilotConfig.from_env()

    assert config.prometheus_base_url == "http://prometheus.monitoring.svc:9090"


def test_from_env_uses_default_rate_limits(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "dev")
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
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "dev")
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
