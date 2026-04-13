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
