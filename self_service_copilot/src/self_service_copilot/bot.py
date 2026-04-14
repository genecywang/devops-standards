from __future__ import annotations

import logging
import os

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from openclaw_foundation.adapters.kubernetes import (
    FakeKubernetesProviderAdapter,
    KubernetesError,
    RealKubernetesProviderAdapter,
    build_apps_v1_api,
    build_core_v1_api,
)
from openclaw_foundation.adapters.prometheus import (
    FakePrometheusProviderAdapter,
    PrometheusQueryError,
    RealPrometheusProviderAdapter,
)
from openclaw_foundation.runtime.runner import OpenClawRunner
from openclaw_foundation.tools.kubernetes_deployment_status import KubernetesDeploymentStatusTool
from openclaw_foundation.tools.kubernetes_pod_events import KubernetesPodEventsTool
from openclaw_foundation.tools.kubernetes_pod_status import KubernetesPodStatusTool
from openclaw_foundation.tools.prometheus_deployment_restart_rate import (
    PrometheusDeploymentRestartRateTool,
)
from openclaw_foundation.tools.prometheus_pod_cpu_usage import PrometheusPodCpuUsageTool
from openclaw_foundation.tools.prometheus_pod_runtime import PrometheusPodRuntimeTool
from openclaw_foundation.tools.registry import ToolRegistry

from self_service_copilot.config import CopilotConfig
from self_service_copilot.dispatcher import DispatchError, SlackContext, build_request
from self_service_copilot.formatter import (
    format_dispatch_error,
    format_parse_error,
    format_platform_error,
    format_response,
)
from self_service_copilot.ownership import OwnershipDecision, decide_ownership
from self_service_copilot.parser import ParseError, parse
from self_service_copilot.rate_limit import (
    CopilotRateLimiter,
    RateLimitExceededError,
    RateLimitRule,
)

logger = logging.getLogger(__name__)


def _log_level_from_env() -> int:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_name, logging.INFO)


def should_handle_channel(channel_id: str, allowed_channel_ids: set[str]) -> bool:
    if not allowed_channel_ids:
        return True
    return channel_id in allowed_channel_ids


def is_expected_platform_error(error: Exception) -> bool:
    return isinstance(error, (KubernetesError, PrometheusQueryError))


def safe_reply(say, message: str, thread_ts: str) -> None:
    try:
        say(message, thread_ts=thread_ts)
    except Exception:
        logger.exception("failed to send Slack reply")


def log_ownership_decision(
    decision: OwnershipDecision,
    *,
    my_environment: str,
    my_cluster: str,
) -> None:
    logger.info(
        "ownership decision source_type=%s target_environment=%s target_cluster=%s "
        "my_environment=%s my_cluster=%s decision=%s reason=%s",
        decision.source_type,
        decision.target_environment,
        decision.target_cluster,
        my_environment,
        my_cluster,
        decision.decision,
        decision.reason,
    )


def build_rate_limiter(config: CopilotConfig) -> CopilotRateLimiter:
    return CopilotRateLimiter(
        user_rule=RateLimitRule(
            limit=config.user_rate_limit_count,
            window_seconds=config.user_rate_limit_window_seconds,
        ),
        channel_rule=RateLimitRule(
            limit=config.channel_rate_limit_count,
            window_seconds=config.channel_rate_limit_window_seconds,
        ),
    )


def build_registry(config: CopilotConfig) -> ToolRegistry:
    if config.provider == "real":
        if not config.prometheus_base_url:
            raise ValueError("OPENCLAW_PROMETHEUS_BASE_URL is required for real provider")
        adapter = RealKubernetesProviderAdapter(build_core_v1_api(), build_apps_v1_api())
        prometheus_adapter = RealPrometheusProviderAdapter(
            base_url=config.prometheus_base_url
        )
    else:
        adapter = FakeKubernetesProviderAdapter()
        prometheus_adapter = FakePrometheusProviderAdapter()

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
    registry.register(
        KubernetesDeploymentStatusTool(
            adapter=adapter,
            allowed_clusters=config.allowed_clusters,
            allowed_namespaces=config.allowed_namespaces,
        )
    )
    registry.register(
        PrometheusPodRuntimeTool(
            adapter=prometheus_adapter,
            allowed_namespaces=config.allowed_namespaces,
        )
    )
    registry.register(
        PrometheusPodCpuUsageTool(
            adapter=prometheus_adapter,
            allowed_namespaces=config.allowed_namespaces,
        )
    )
    registry.register(
        PrometheusDeploymentRestartRateTool(
            adapter=prometheus_adapter,
            allowed_namespaces=config.allowed_namespaces,
        )
    )
    return registry


def handle_mention_event(
    *,
    event,
    say,
    config: CopilotConfig,
    bot_user_id: str,
    runner,
    limiter: CopilotRateLimiter,
) -> None:
    text = event.get("text", "")
    event_ts = event.get("ts", "")
    channel_id = event.get("channel", "")
    actor_id = event.get("user", "")
    logger.info(
        "received app_mention channel=%s user=%s text=%r",
        channel_id,
        actor_id,
        text,
    )
    if not should_handle_channel(channel_id, config.allowed_channel_ids):
        logger.info(
            "ignored mention from disallowed channel channel=%s user=%s",
            channel_id,
            actor_id,
        )
        return

    try:
        limiter.check(actor_id=actor_id, channel_id=channel_id)
    except RateLimitExceededError:
        logger.info("rate limit exceeded for actor=%s channel=%s", actor_id, channel_id)
        safe_reply(say, "[denied] rate limit exceeded, please retry later", event_ts)
        return

    ownership_decision = decide_ownership(
        text=text,
        bot_user_id=bot_user_id,
        supported_tools=config.supported_tools,
        my_environment=config.environment,
        my_cluster=config.cluster,
    )
    log_ownership_decision(
        ownership_decision,
        my_environment=config.environment,
        my_cluster=config.cluster,
    )
    if ownership_decision.decision == "ignored":
        return
    if ownership_decision.source_type == "prometheus_alert":
        return

    ctx = SlackContext(actor_id=actor_id, channel_id=channel_id, event_ts=event_ts)

    try:
        cmd = parse(text, bot_user_id, config.supported_tools)
    except ParseError as error:
        safe_reply(say, format_parse_error(error, config.supported_tools), event_ts)
        return

    try:
        request = build_request(cmd, ctx, config)
    except DispatchError as error:
        logger.info(
            "dispatch denied actor=%s channel=%s tool=%s namespace=%s resource_name=%s reason=%s",
            actor_id,
            channel_id,
            cmd.tool_name,
            cmd.namespace,
            cmd.resource_name,
            error,
        )
        safe_reply(say, format_dispatch_error(error, cmd), event_ts)
        return

    try:
        response = runner.run(request)
        safe_reply(say, format_response(response, cmd), event_ts)
    except Exception as error:
        if is_expected_platform_error(error):
            logger.info("platform error while handling Slack mention: %s", error)
            safe_reply(say, format_platform_error(error, cmd), event_ts)
            return
        logger.exception("unexpected failure while handling Slack mention")
        safe_reply(say, "[error] unexpected failure, please retry", event_ts)


def main() -> None:
    logging.basicConfig(level=_log_level_from_env())

    config = CopilotConfig.from_env()
    registry = build_registry(config)
    runner = OpenClawRunner(registry)
    limiter = build_rate_limiter(config)

    app = App(token=os.environ["SLACK_BOT_TOKEN"])
    bot_user_id: str = app.client.auth_test()["user_id"]

    @app.event("app_mention")
    def handle_mention(event, say) -> None:
        handle_mention_event(
            event=event,
            say=say,
            config=config,
            bot_user_id=bot_user_id,
            runner=runner,
            limiter=limiter,
        )

    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()


if __name__ == "__main__":
    main()
