import pytest

from self_service_copilot.parser import (
    ParsedCommand,
    UnknownCommandError,
    UsageError,
    parse,
)

SUPPORTED = frozenset({"get_pod_status", "get_pod_events"})
BOT_ID = "U123456"


def test_parse_returns_parsed_command_for_valid_input() -> None:
    raw = f"<@{BOT_ID}> get_pod_status payments payments-api-123"
    cmd = parse(raw, BOT_ID, SUPPORTED)

    assert cmd == ParsedCommand(
        tool_name="get_pod_status",
        namespace="payments",
        resource_name="payments-api-123",
        raw_text=raw,
    )


def test_parse_strips_extra_whitespace() -> None:
    cmd = parse(f"<@{BOT_ID}>   get_pod_events   payments   payments-api-123  ", BOT_ID, SUPPORTED)

    assert cmd.tool_name == "get_pod_events"
    assert cmd.namespace == "payments"
    assert cmd.resource_name == "payments-api-123"


def test_parse_supports_environment_prefix() -> None:
    cmd = parse(
        f"<@{BOT_ID}> au get_pod_status payments payments-api-123",
        BOT_ID,
        SUPPORTED,
    )

    assert cmd.requested_environment == "au"
    assert cmd.tool_name == "get_pod_status"
    assert cmd.namespace == "payments"
    assert cmd.resource_name == "payments-api-123"


def test_parse_raises_unknown_command_error_for_unrecognised_tool() -> None:
    with pytest.raises(UnknownCommandError, match="get_pod_logs"):
        parse(f"<@{BOT_ID}> get_pod_logs payments payments-api-123", BOT_ID, SUPPORTED)


def test_parse_raises_usage_error_for_too_few_arguments() -> None:
    with pytest.raises(UsageError):
        parse(f"<@{BOT_ID}> get_pod_status payments", BOT_ID, SUPPORTED)


def test_parse_raises_usage_error_for_too_many_arguments() -> None:
    with pytest.raises(UsageError):
        parse(f"<@{BOT_ID}> get_pod_status payments pod-123 extra", BOT_ID, SUPPORTED)


def test_parse_raises_usage_error_for_empty_mention() -> None:
    with pytest.raises(UsageError):
        parse(f"<@{BOT_ID}>", BOT_ID, SUPPORTED)


def test_parse_preserves_raw_text() -> None:
    raw = f"<@{BOT_ID}> get_pod_status payments payments-api-123"
    cmd = parse(raw, BOT_ID, SUPPORTED)

    assert cmd.raw_text == raw
    assert cmd.requested_environment is None
