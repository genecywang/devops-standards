from openclaw_foundation.models.requests import ExecutionBudget

from self_service_copilot.bot import build_registry, should_handle_channel
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
