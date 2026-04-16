from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from alert_auto_investigator.ingress import (
    parse_alertmanager_slack_message,
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


def _detect_alert(
    texts: list[str],
    region_code: str,
    fallback_environment: str,
) -> NormalizedAlertEvent | None:
    for text in texts:
        result = parse_cloudwatch_slack_message(text)
        if result:
            return result
        result = parse_alertmanager_slack_message(text, region_code, fallback_environment)
        if result:
            return result
    return None


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

    Guards → text extraction → alert detection → control pipeline →
    dispatch → record → Slack thread reply.
    """
    # Guard: ignore only messages posted by this bot itself.
    # Incoming webhooks from Alertmanager / CloudWatch also carry bot_id and
    # must still be processed.
    if own_bot_id is not None and event.get("bot_id") == own_bot_id:
        return
    if own_bot_user_id is not None and event.get("user") == own_bot_user_id:
        return
    if event.get("subtype") == "bot_message" and event.get("bot_id") == own_bot_id:
        return
    if not _should_handle_channel(event.get("channel", ""), config.allowed_channel_ids):
        return

    texts = _extract_texts(event)
    alert = _detect_alert(texts, config.region_code, config.fallback_environment)
    if alert is None:
        return  # not a structured alert — silent skip, do not reply

    decision = pipeline.evaluate(alert)
    if decision.action != ControlAction.INVESTIGATE:
        logger.info("skip alert_key=%s reason=%s", alert.alert_key, decision.reason)
        return

    try:
        response = dispatcher.dispatch(alert)
    except Exception:
        logger.exception(
            "dispatch failed alert_key=%s resource_type=%s resource_name=%s",
            alert.alert_key,
            alert.resource_type,
            alert.resource_name,
        )
        return
    if response is None:
        logger.info(
            "no tool mapped resource_type=%s alert_key=%s",
            alert.resource_type,
            alert.alert_key,
        )
        return

    # Record only after a successful dispatch to avoid poisoning cooldown
    pipeline.record_investigation(alert)

    client.chat_postMessage(  # type: ignore[union-attr]
        channel=event["channel"],
        thread_ts=_reply_ts(event),
        text=format_investigation_reply(alert, response),
    )
