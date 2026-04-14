from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedCommand:
    tool_name: str
    namespace: str
    resource_name: str
    raw_text: str
    requested_environment: str | None = None


class ParseError(ValueError):
    pass


class UnknownCommandError(ParseError):
    pass


class UsageError(ParseError):
    pass


def parse(text: str, bot_user_id: str, supported_tools: frozenset[str]) -> ParsedCommand:
    raw_text = text
    cleaned = re.sub(rf"<@{re.escape(bot_user_id)}>", "", text).strip()
    tokens = cleaned.split()

    if len(tokens) not in {3, 4}:
        raise UsageError(
            "expected: [environment] <tool_name> <namespace> <resource_name>, "
            f"got {len(tokens)} token(s)"
        )

    requested_environment: str | None = None
    if len(tokens) == 4:
        if tokens[0] in supported_tools:
            raise UsageError(
                "expected: [environment] <tool_name> <namespace> <resource_name>, "
                f"got {len(tokens)} token(s)"
            )
        requested_environment, tool_name, namespace, resource_name = tokens
    else:
        tool_name, namespace, resource_name = tokens

    if tool_name not in supported_tools:
        raise UnknownCommandError(tool_name)

    return ParsedCommand(
        tool_name=tool_name,
        namespace=namespace,
        resource_name=resource_name,
        raw_text=raw_text,
        requested_environment=requested_environment,
    )
