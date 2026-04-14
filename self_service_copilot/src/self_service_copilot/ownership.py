from __future__ import annotations

from dataclasses import dataclass
import re

from self_service_copilot.parser import ParseError, parse


@dataclass(frozen=True)
class OwnershipDecision:
    source_type: str
    decision: str
    reason: str
    target_environment: str | None = None
    target_cluster: str | None = None


_ALERT_FIELD_RE_TEMPLATE = r"^{}:\s*(?P<value>.+?)\s*$"


def _extract_field(text: str, field_name: str) -> str | None:
    match = re.search(_ALERT_FIELD_RE_TEMPLATE.format(re.escape(field_name)), text, re.MULTILINE)
    if match is None:
        return None
    return match.group("value").strip() or None


def _looks_like_manual_command(text: str, bot_user_id: str) -> bool:
    return f"<@{bot_user_id}>" in text


def decide_ownership(
    *,
    text: str,
    bot_user_id: str,
    supported_tools: frozenset[str],
    my_environment: str,
    my_cluster: str,
) -> OwnershipDecision:
    if _looks_like_manual_command(text, bot_user_id):
        try:
            cmd = parse(text, bot_user_id, supported_tools)
        except ParseError:
            return OwnershipDecision(
                source_type="manual_command",
                decision="handled",
                reason="parse_required",
            )

        if cmd.requested_environment is None:
            return OwnershipDecision(
                source_type="manual_command",
                decision="handled",
                reason="default_environment_path",
            )

        if cmd.requested_environment != my_environment:
            return OwnershipDecision(
                source_type="manual_command",
                decision="ignored",
                reason="not_my_environment",
                target_environment=cmd.requested_environment,
            )

        return OwnershipDecision(
            source_type="manual_command",
            decision="handled",
            reason="environment_match",
            target_environment=cmd.requested_environment,
        )

    alert_source = _extract_field(text, "AlertSource")
    cluster = _extract_field(text, "Cluster")
    if alert_source == "prometheus" and cluster is not None:
        if cluster == my_cluster:
            return OwnershipDecision(
                source_type="prometheus_alert",
                decision="handled",
                reason="cluster_match",
                target_cluster=cluster,
            )

        return OwnershipDecision(
            source_type="prometheus_alert",
            decision="ignored",
            reason="not_my_cluster",
            target_cluster=cluster,
        )

    return OwnershipDecision(
        source_type="unknown",
        decision="ignored",
        reason="unroutable",
    )
