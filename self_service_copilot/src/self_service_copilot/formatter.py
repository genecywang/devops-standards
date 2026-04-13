from __future__ import annotations

from openclaw_foundation.adapters.kubernetes import (
    KubernetesAccessDeniedError,
    KubernetesApiError,
    KubernetesConfigError,
    KubernetesEndpointUnreachableError,
    KubernetesResourceNotFoundError,
)
from openclaw_foundation.adapters.prometheus import PrometheusQueryError
from openclaw_foundation.models.enums import ResultState
from openclaw_foundation.models.responses import CanonicalResponse

from self_service_copilot.dispatcher import DispatchError
from self_service_copilot.parser import ParsedCommand, ParseError, UnknownCommandError


def _resource_label(cmd: ParsedCommand) -> str:
    return f"{cmd.tool_name} {cmd.namespace}/{cmd.resource_name}"


def format_response(response: CanonicalResponse, cmd: ParsedCommand) -> str:
    label = _resource_label(cmd)
    if response.result_state == ResultState.SUCCESS:
        return f"[success] {label}\n{response.summary}"
    if response.result_state == ResultState.FAILED:
        return f"[failed] {label}\n{response.summary}"
    if response.result_state == ResultState.FALLBACK:
        return f"[fallback] {label}\n{response.summary}"
    return f"[{response.result_state}] {label}\n{response.summary}"


def format_parse_error(error: ParseError, supported_tools: frozenset[str]) -> str:
    supported_str = ", ".join(
        f"{t} <namespace> <resource_name>" for t in sorted(supported_tools)
    )
    if isinstance(error, UnknownCommandError):
        return f"[unknown command] {error}\nSupported: {supported_str}"
    return f"[usage] {error}\nSupported: {supported_str}"


def format_dispatch_error(error: DispatchError, cmd: ParsedCommand) -> str:
    return f"[denied] {error}"


def format_platform_error(error: Exception, cmd: ParsedCommand) -> str:
    label = _resource_label(cmd)
    if isinstance(error, KubernetesAccessDeniedError):
        return f"[denied] {label}\n{error}"
    if isinstance(error, KubernetesResourceNotFoundError):
        return f"[failed] {label}\n{error}"
    if isinstance(error, KubernetesEndpointUnreachableError):
        return (
            f"[failed] {label}\n{error}\n"
            "next check: verify DNS, network path, VPN, or cluster endpoint"
        )
    if isinstance(error, (KubernetesApiError, KubernetesConfigError, PrometheusQueryError)):
        return f"[failed] {label}\n{error}"
    return f"[error] {label}\nunexpected failure, please retry"
