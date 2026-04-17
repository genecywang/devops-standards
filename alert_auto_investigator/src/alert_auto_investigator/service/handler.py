from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from alert_auto_investigator.ingress import (
    parse_alertmanager_slack_messages,
    parse_cloudwatch_slack_message,
)
from alert_auto_investigator.models.control_decision import ControlAction
from alert_auto_investigator.models.normalized_alert_event import NormalizedAlertEvent
from alert_auto_investigator.service.formatter import format_investigation_reply

if TYPE_CHECKING:
    from alert_auto_investigator.config import InvestigatorConfig
    from alert_auto_investigator.control.pipeline import ControlPipeline
    from alert_auto_investigator.investigation.dispatcher import OpenClawDispatcher

logger = logging.getLogger(__name__)


def _should_handle_channel(channel_id: str, allowed_channel_ids: list[str] | None) -> bool:
    if not allowed_channel_ids:
        return True
    return channel_id in allowed_channel_ids


def _extract_texts(event: dict) -> list[str]:
    """Return candidate alert texts from a Slack event.

    Priority: attachment texts (where both Alertmanager and CloudWatch put
    their content) → fallback to top-level event text.
    """
    texts = [a["text"] for a in event.get("attachments", []) if a.get("text")]
    if not texts:
        fallback = event.get("text", "")
        if fallback:
            texts.append(fallback)
    return texts


def _reply_ts(event: dict) -> str:
    """Return the Slack timestamp to reply to.

    Uses thread_ts when the message is already in a thread so the reply
    stays in that thread; otherwise uses ts to open a new thread on the
    original message.
    """
    return event.get("thread_ts") or event["ts"]


def _detect_alerts(
    texts: list[str],
    region_code: str,
    fallback_environment: str,
) -> list[NormalizedAlertEvent]:
    """Return all parseable NormalizedAlertEvents from a list of candidate texts.

    CloudWatch messages produce at most one alert per text. Alertmanager messages
    may contain multiple alerts (FIRING:N); all are returned.
    """
    alerts: list[NormalizedAlertEvent] = []
    for text in texts:
        cw = parse_cloudwatch_slack_message(text)
        if cw is not None:
            alerts.append(cw)
            continue
        am_alerts = parse_alertmanager_slack_messages(text, region_code, fallback_environment)
        alerts.extend(am_alerts)
    return alerts


def handle_message(
    event: dict,
    client: object,
    config: InvestigatorConfig,
    pipeline: ControlPipeline,
    dispatcher: OpenClawDispatcher,
    own_bot_id: str | None = None,
    own_bot_user_id: str | None = None,
) -> None:
    """Process a single Slack message event.

    Guards → text extraction → alert detection → for each alert:
    control pipeline → dispatch → record → Slack thread reply.
    """
    if own_bot_id is not None and event.get("bot_id") == own_bot_id:
        return
    if own_bot_user_id is not None and event.get("user") == own_bot_user_id:
        return
    if event.get("subtype") == "bot_message" and event.get("bot_id") == own_bot_id:
        return
    if not _should_handle_channel(event.get("channel", ""), config.allowed_channel_ids):
        return

    texts = _extract_texts(event)
    alerts = _detect_alerts(texts, config.region_code, config.fallback_environment)
    if not alerts:
        return  # not a structured alert — silent skip, do not reply

    reply_ts = _reply_ts(event)

    for alert in alerts:
        decision = pipeline.evaluate(alert)
        if decision.action != ControlAction.INVESTIGATE:
            logger.info("skip alert_key=%s reason=%s", alert.alert_key, decision.reason)
            continue

        try:
            response = dispatcher.dispatch(alert)
        except Exception:
            logger.exception(
                "dispatch failed alert_key=%s resource_type=%s resource_name=%s",
                alert.alert_key,
                alert.resource_type,
                alert.resource_name,
            )
            continue
        if response is None:
            # dispatcher already logs the specific reason (skip_by_design / next_candidate / unknown)
            continue

        # Record only after a successful dispatch to avoid poisoning cooldown
        pipeline.record_investigation(alert)

        client.chat_postMessage(  # type: ignore[union-attr]
            channel=event["channel"],
            thread_ts=reply_ts,
            text=format_investigation_reply(alert, response),
        )
