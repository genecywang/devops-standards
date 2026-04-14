from openclaw_foundation.adapters.kubernetes import (
    KubernetesEndpointUnreachableError,
    KubernetesResourceNotFoundError,
)
from openclaw_foundation.adapters.prometheus import PrometheusQueryError
from openclaw_foundation.models.enums import ResultState
from openclaw_foundation.models.responses import CanonicalResponse

from self_service_copilot.dispatcher import DispatchError
from self_service_copilot.formatter import (
    format_dispatch_error,
    format_parse_error,
    format_platform_error,
    format_response,
)
from self_service_copilot.parser import ParsedCommand, UnknownCommandError, UsageError

SUPPORTED = frozenset({"get_pod_status", "get_pod_events"})


def make_cmd(tool_name: str = "get_pod_status") -> ParsedCommand:
    return ParsedCommand(
        tool_name=tool_name,
        namespace="payments",
        resource_name="payments-api-123",
        raw_text=f"<@BOT> {tool_name} payments payments-api-123",
    )


def make_response(result_state: ResultState, summary: str = "pod payments-api-123 is Running") -> CanonicalResponse:
    return CanonicalResponse(
        request_id="slack:C001:1234",
        result_state=result_state,
        summary=summary,
        actions_attempted=["get_pod_status"],
        redaction_applied=True,
    )


def test_format_response_success_starts_with_success_label() -> None:
    reply = format_response(make_response(ResultState.SUCCESS), make_cmd())

    assert reply.startswith("[success]")


def test_format_response_success_includes_tool_and_resource_label() -> None:
    reply = format_response(make_response(ResultState.SUCCESS), make_cmd())

    assert "get_pod_status" in reply
    assert "payments/payments-api-123" in reply


def test_format_response_success_includes_summary() -> None:
    reply = format_response(make_response(ResultState.SUCCESS), make_cmd())

    assert "pod payments-api-123 is Running" in reply


def test_format_response_failed_starts_with_failed_label() -> None:
    reply = format_response(
        make_response(ResultState.FAILED, "no registered tool available for get_pod_status"),
        make_cmd(),
    )

    assert reply.startswith("[failed]")
    assert "no registered tool available" in reply


def test_format_response_fallback_starts_with_fallback_label() -> None:
    reply = format_response(
        make_response(ResultState.FALLBACK, "budget exhausted before tool execution"),
        make_cmd(),
    )

    assert reply.startswith("[fallback]")
    assert "budget exhausted" in reply


def test_format_parse_error_unknown_command_starts_with_unknown_label() -> None:
    error = UnknownCommandError("get_pod_logs")
    reply = format_parse_error(error, SUPPORTED)

    assert reply.startswith("[unknown command]")
    assert "get_pod_logs" in reply


def test_format_parse_error_unknown_command_lists_supported_tools_sorted() -> None:
    error = UnknownCommandError("get_pod_logs")
    reply = format_parse_error(error, SUPPORTED)

    idx_events = reply.index("get_pod_events")
    idx_status = reply.index("get_pod_status")
    assert idx_events < idx_status


def test_format_parse_error_usage_error_starts_with_usage_label() -> None:
    error = UsageError("expected: <tool_name> <namespace> <resource_name>, got 1 token(s)")
    reply = format_parse_error(error, SUPPORTED)

    assert reply.startswith("[usage]")


def test_format_dispatch_error_starts_with_denied_label() -> None:
    error = DispatchError('namespace "internal" is not allowed')
    reply = format_dispatch_error(error, make_cmd())

    assert reply.startswith("[denied]")
    assert "internal" in reply


def test_format_dispatch_error_for_invalid_resource_name_uses_denied_label() -> None:
    error = DispatchError("resource_name 'payments-api-123;' is not allowed")
    reply = format_dispatch_error(error, make_cmd())

    assert reply.startswith("[denied]")
    assert "resource_name" in reply


def test_format_platform_error_for_prometheus_query_error_uses_failed_label() -> None:
    reply = format_platform_error(PrometheusQueryError("no metrics found for pod"), make_cmd("get_pod_runtime"))

    assert reply.startswith("[failed]")
    assert "get_pod_runtime" in reply
    assert "no metrics found for pod" in reply


def test_format_platform_error_for_kubernetes_not_found_uses_failed_label() -> None:
    reply = format_platform_error(
        KubernetesResourceNotFoundError("pod not found"),
        make_cmd(),
    )

    assert reply.startswith("[failed]")
    assert "pod not found" in reply


def test_format_platform_error_for_endpoint_issue_includes_next_check() -> None:
    reply = format_platform_error(
        KubernetesEndpointUnreachableError("cluster endpoint unreachable"),
        make_cmd(),
    )

    assert reply.startswith("[failed]")
    assert "next check:" in reply
