"""Entry point for the Alert Auto-Investigator Slack bot.

Usage:
    python -m alert_auto_investigator

Required env vars:
    SLACK_BOT_TOKEN       xoxb-... bot token
    SLACK_APP_TOKEN       xapp-... app-level token (Socket Mode)
    REGION_CODE           e.g. ap-east-1
    FALLBACK_ENVIRONMENT  e.g. dev
    OWNED_ENVIRONMENTS    comma-separated, e.g. dev,staging

Optional env vars (with defaults):
    COOLDOWN_SECONDS          300
    RATE_LIMIT_COUNT          10
    RATE_LIMIT_WINDOW_SECONDS 3600
    INVESTIGATE_ALLOWLIST     comma-separated alert names; empty = allow all
    INVESTIGATE_DENYLIST      comma-separated alert names to always skip
"""

import logging

from alert_auto_investigator.config import InvestigatorConfig
from alert_auto_investigator.control.pipeline import ControlPipeline
from alert_auto_investigator.control.store import InMemoryAlertStateStore
from alert_auto_investigator.investigation.dispatcher import InvestigationConfig, OpenClawDispatcher
from alert_auto_investigator.models.control_policy import ControlPolicy
from alert_auto_investigator.service.handler import handle_message
from alert_auto_investigator.service.runner_factory import build_runner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def _load_slack_bolt() -> tuple[object, object]:
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    return App, SocketModeHandler


def main() -> None:
    config = InvestigatorConfig.from_env()
    App, SocketModeHandler = _load_slack_bolt()

    policy = ControlPolicy(
        owned_environments=frozenset(config.owned_environments),
        investigate_allowlist=frozenset(config.investigate_allowlist),
        investigate_denylist=frozenset(config.investigate_denylist),
        cooldown_seconds=config.cooldown_seconds,
        rate_limit_count=config.rate_limit_count,
        rate_limit_window_seconds=config.rate_limit_window_seconds,
    )
    pipeline = ControlPipeline(policy, InMemoryAlertStateStore())

    investigation_config = InvestigationConfig(
        tool_routing={
            "pod": "get_pod_events",
            "deployment": "get_deployment_status",
        }
    )
    dispatcher = OpenClawDispatcher(build_runner(config), investigation_config)

    app = App(token=config.slack_bot_token)
    auth_info = app.client.auth_test()
    own_bot_id = auth_info.get("bot_id")
    own_bot_user_id = auth_info.get("user_id")

    @app.event("message")
    def on_message(event: dict, client: object) -> None:
        handle_message(
            event,
            client,
            config,
            pipeline,
            dispatcher,
            own_bot_id=own_bot_id,
            own_bot_user_id=own_bot_user_id,
        )

    logger.info(
        "starting alert-auto-investigator env=%s region=%s bot_id=%s",
        config.fallback_environment,
        config.region_code,
        own_bot_id,
    )
    SocketModeHandler(app, config.slack_app_token).start()


if __name__ == "__main__":
    main()
