from __future__ import annotations

from dataclasses import dataclass

from self_service_copilot.parser import ParseError, parse


@dataclass(frozen=True)
class OwnershipDecision:
    source_type: str
    decision: str
    reason: str
    target_environment: str | None = None


def _looks_like_manual_command(text: str, bot_user_id: str) -> bool:
    return f"<@{bot_user_id}>" in text


def decide_ownership(
    *,
    text: str,
    bot_user_id: str,
    supported_tools: frozenset[str],
    my_environment: str,
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

    return OwnershipDecision(
        source_type="unknown",
        decision="ignored",
        reason="unroutable",
    )
