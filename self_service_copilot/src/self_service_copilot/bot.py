from __future__ import annotations

import logging
import os

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from openclaw_foundation.adapters.kubernetes import (
    FakeKubernetesProviderAdapter,
    RealKubernetesProviderAdapter,
    build_core_v1_api,
)
from openclaw_foundation.runtime.runner import OpenClawRunner
from openclaw_foundation.tools.kubernetes_pod_events import KubernetesPodEventsTool
from openclaw_foundation.tools.kubernetes_pod_status import KubernetesPodStatusTool
from openclaw_foundation.tools.registry import ToolRegistry

from self_service_copilot.config import CopilotConfig
from self_service_copilot.dispatcher import DispatchError, SlackContext, build_request
from self_service_copilot.formatter import (
    format_dispatch_error,
    format_parse_error,
    format_response,
)
from self_service_copilot.parser import ParseError, parse

logger = logging.getLogger(__name__)


def build_registry(config: CopilotConfig) -> ToolRegistry:
    if config.provider == "real":
        adapter = RealKubernetesProviderAdapter(build_core_v1_api())
    else:
        adapter = FakeKubernetesProviderAdapter()

    registry = ToolRegistry()
    registry.register(
        KubernetesPodStatusTool(
            adapter=adapter,
            allowed_clusters=config.allowed_clusters,
            allowed_namespaces=config.allowed_namespaces,
        )
    )
    registry.register(
        KubernetesPodEventsTool(
            adapter=adapter,
            allowed_clusters=config.allowed_clusters,
            allowed_namespaces=config.allowed_namespaces,
        )
    )
    return registry


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    config = CopilotConfig.from_env()
    registry = build_registry(config)
    runner = OpenClawRunner(registry)

    app = App(token=os.environ["SLACK_BOT_TOKEN"])
    bot_user_id: str = app.client.auth_test()["user_id"]

    def safe_reply(say, message: str, thread_ts: str) -> None:
        try:
            say(message, thread_ts=thread_ts)
        except Exception:
            logger.exception("failed to send Slack reply")

    @app.event("app_mention")
    def handle_mention(event, say) -> None:
        text = event.get("text", "")
        event_ts = event.get("ts", "")
        channel_id = event.get("channel", "")
        actor_id = event.get("user", "")
        ctx = SlackContext(actor_id=actor_id, channel_id=channel_id, event_ts=event_ts)

        try:
            cmd = parse(text, bot_user_id, config.supported_tools)
        except ParseError as error:
            safe_reply(say, format_parse_error(error, config.supported_tools), event_ts)
            return

        try:
            request = build_request(cmd, ctx, config)
        except DispatchError as error:
            safe_reply(say, format_dispatch_error(error, cmd), event_ts)
            return

        try:
            response = runner.run(request)
            safe_reply(say, format_response(response, cmd), event_ts)
        except Exception:
            logger.exception("unexpected failure while handling Slack mention")
            safe_reply(say, "[error] unexpected failure, please retry", event_ts)

    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()


if __name__ == "__main__":
    main()
