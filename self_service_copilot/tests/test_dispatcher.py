import pytest

from openclaw_foundation.models.requests import ExecutionBudget

from self_service_copilot.config import CopilotConfig
from self_service_copilot.dispatcher import (
    DispatchError,
    SlackContext,
    build_request,
    make_request_id,
)
from self_service_copilot.parser import ParsedCommand


def make_config(**overrides) -> CopilotConfig:
    defaults = dict(
        cluster="staging-main",
        environment="staging",
        default_environment="staging",
        environment_clusters={"staging": "staging-main"},
        allowed_clusters={"staging-main"},
        allowed_namespaces={"dev"},
        supported_tools=frozenset({"get_pod_status", "get_pod_events"}),
        default_budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=15,
            max_output_tokens=512,
        ),
        provider="fake",
    )
    defaults.update(overrides)
    return CopilotConfig(**defaults)


def make_cmd(tool_name: str = "get_pod_status", namespace: str = "dev") -> ParsedCommand:
    return ParsedCommand(
        tool_name=tool_name,
        namespace=namespace,
        resource_name="dev-api-123",
        raw_text=f"@copilot {tool_name} {namespace} dev-api-123",
        requested_environment=None,
    )


def make_ctx() -> SlackContext:
    return SlackContext(actor_id="U999", channel_id="C001", event_ts="1234567890.000100")


def test_make_request_id_encodes_channel_and_ts() -> None:
    ctx = SlackContext(actor_id="U999", channel_id="C001", event_ts="1234567890.000100")

    assert make_request_id(ctx) == "slack:C001:1234567890.000100"


def test_build_request_sets_request_id_from_context() -> None:
    request = build_request(make_cmd(), make_ctx(), make_config())

    assert request.request_id == "slack:C001:1234567890.000100"


def test_build_request_sets_input_ref_from_context() -> None:
    request = build_request(make_cmd(), make_ctx(), make_config())

    assert request.input_ref == "slack://C001/1234567890.000100"


def test_build_request_sets_source_product() -> None:
    request = build_request(make_cmd(), make_ctx(), make_config())

    assert request.source_product == "self_service_copilot"


def test_build_request_sets_requested_by_from_actor_id() -> None:
    request = build_request(make_cmd(), make_ctx(), make_config())

    assert request.requested_by == "U999"


def test_build_request_cluster_always_from_config_not_user_input() -> None:
    request = build_request(make_cmd(), make_ctx(), make_config())

    assert request.scope["cluster"] == "staging-main"
    assert request.target["cluster"] == "staging-main"


def test_build_request_target_contains_namespace_and_resource_name() -> None:
    request = build_request(make_cmd(), make_ctx(), make_config())

    assert request.target["namespace"] == "dev"
    assert request.target["resource_name"] == "dev-api-123"


def test_build_request_uses_default_environment_when_not_specified() -> None:
    request = build_request(make_cmd(), make_ctx(), make_config())

    assert request.scope["environment"] == "staging"


def test_build_request_uses_requested_environment_and_cluster_mapping() -> None:
    cmd = ParsedCommand(
        tool_name="get_pod_status",
        namespace="dev",
        resource_name="dev-api-123",
        raw_text="@copilot jp get_pod_status dev dev-api-123",
        requested_environment="jp",
    )
    config = make_config(
        default_environment="staging",
        environment_clusters={"staging": "staging-main", "jp": "jp-main"},
        allowed_clusters={"staging-main", "jp-main"},
    )

    request = build_request(cmd, make_ctx(), config)

    assert request.scope["environment"] == "jp"
    assert request.scope["cluster"] == "jp-main"
    assert request.target["cluster"] == "jp-main"


def test_build_request_raises_dispatch_error_for_disallowed_tool() -> None:
    cmd = make_cmd(tool_name="get_pod_logs")

    with pytest.raises(DispatchError, match="get_pod_logs"):
        build_request(cmd, make_ctx(), make_config())


def test_build_request_raises_dispatch_error_for_disallowed_namespace() -> None:
    cmd = make_cmd(namespace="internal")

    with pytest.raises(DispatchError, match="internal"):
        build_request(cmd, make_ctx(), make_config())


def test_build_request_raises_dispatch_error_for_invalid_resource_name() -> None:
    cmd = ParsedCommand(
        tool_name="get_pod_status",
        namespace="dev",
        resource_name="dev-api-123;",
        raw_text="@copilot get_pod_status dev dev-api-123;",
        requested_environment=None,
    )

    with pytest.raises(DispatchError, match="resource_name"):
        build_request(cmd, make_ctx(), make_config())


def test_build_request_raises_dispatch_error_for_unknown_environment() -> None:
    cmd = ParsedCommand(
        tool_name="get_pod_status",
        namespace="dev",
        resource_name="dev-api-123",
        raw_text="@copilot au get_pod_status dev dev-api-123",
        requested_environment="au",
    )

    with pytest.raises(DispatchError, match="environment"):
        build_request(cmd, make_ctx(), make_config())


def test_build_request_raises_dispatch_error_when_cluster_not_in_allowlist() -> None:
    config = make_config(allowed_clusters={"prod-main"})

    with pytest.raises(DispatchError, match="staging-main"):
        build_request(make_cmd(), make_ctx(), config)
