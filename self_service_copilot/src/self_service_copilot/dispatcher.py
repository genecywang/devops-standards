from __future__ import annotations

import re
from dataclasses import dataclass

from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import InvestigationRequest

from self_service_copilot.config import CopilotConfig
from self_service_copilot.parser import ParsedCommand


@dataclass(frozen=True)
class SlackContext:
    actor_id: str
    channel_id: str
    event_ts: str


class DispatchError(ValueError):
    pass


_RESOURCE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def make_request_id(ctx: SlackContext) -> str:
    return f"slack:{ctx.channel_id}:{ctx.event_ts}"


def build_request(
    cmd: ParsedCommand,
    ctx: SlackContext,
    config: CopilotConfig,
) -> InvestigationRequest:
    selected_environment = cmd.requested_environment or config.default_environment
    selected_cluster = config.environment_clusters.get(selected_environment)

    if cmd.tool_name not in config.supported_tools:
        raise DispatchError(f"tool {cmd.tool_name!r} is not allowed")
    if cmd.namespace not in config.allowed_namespaces:
        raise DispatchError(f"namespace {cmd.namespace!r} is not allowed")
    if selected_cluster is None:
        raise DispatchError(f"environment {selected_environment!r} is not allowed")
    if selected_cluster not in config.allowed_clusters:
        raise DispatchError(f"cluster {selected_cluster!r} is not allowed")
    if not _RESOURCE_NAME_PATTERN.fullmatch(cmd.resource_name):
        raise DispatchError(f"resource_name {cmd.resource_name!r} is not allowed")

    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id=make_request_id(ctx),
        input_ref=f"slack://{ctx.channel_id}/{ctx.event_ts}",
        source_product="self_service_copilot",
        requested_by=ctx.actor_id,
        scope={
            "cluster": selected_cluster,
            "environment": selected_environment,
        },
        budget=config.default_budget,
        tool_name=cmd.tool_name,
        target={
            "cluster": selected_cluster,
            "namespace": cmd.namespace,
            "resource_name": cmd.resource_name,
        },
    )
