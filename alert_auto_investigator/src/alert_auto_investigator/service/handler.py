from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from alert_auto_investigator.ingress import (
    parse_alertmanager_slack_messages,
    parse_cloudwatch_slack_message,
)
from alert_auto_investigator.investigation.target_group_enrichment import enrich_target_group_response
from alert_auto_investigator.models.control_decision import ControlAction
from alert_auto_investigator.models.normalized_alert_event import NormalizedAlertEvent
from alert_auto_investigator.service.formatter import format_investigation_reply
from alert_auto_investigator.service.logging_utils import control_reason_code

if TYPE_CHECKING:
    from alert_auto_investigator.assist.service import ReadonlyAssistService
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


def _metadata_log_fields(response: object) -> tuple[str, bool, bool, str]:
    metadata = getattr(response, "metadata", {}) or {}
    health_state = str(metadata.get("health_state") or "unknown")
    attention_required = bool(metadata.get("attention_required", False))
    resource_exists = bool(metadata.get("resource_exists", True))
    primary_reason = str(metadata.get("primary_reason") or "unknown")
    return health_state, attention_required, resource_exists, primary_reason


def _analysis_payload(result: object) -> dict[str, object] | None:
    response = getattr(result, "response", None)
    if response is None:
        return None

    payload: dict[str, object] = {
        "summary": getattr(response, "summary", ""),
        "current_interpretation": getattr(response, "current_interpretation", ""),
        "recommended_next_step": getattr(response, "recommended_next_step", ""),
        "confidence": getattr(response, "confidence", ""),
        "caveats": getattr(response, "caveats", []),
    }
    return payload


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
    kubernetes_adapter: object | None = None,
    assist_service: ReadonlyAssistService | None = None,
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
    logger.info(
        "alerts_detected count=%s channel=%s reply_ts=%s",
        len(alerts),
        event.get("channel", ""),
        _reply_ts(event),
    )

    reply_ts = _reply_ts(event)

    for alert in alerts:
        decision = pipeline.evaluate(alert)
        reason_code = control_reason_code(decision.reason)
        logger.info(
            "control_decision action=%s reason_code=%s alert_key=%s resource_type=%s resource_name=%s reason=%s",
            decision.action.value,
            reason_code,
            alert.alert_key,
            alert.resource_type,
            alert.resource_name,
            decision.reason,
        )
        if decision.action != ControlAction.INVESTIGATE:
            continue

        try:
            response = dispatcher.dispatch(alert)
        except PermissionError as exc:
            logger.info(
                "dispatch_scope_denied alert_key=%s resource_type=%s resource_name=%s reason=%s",
                alert.alert_key,
                alert.resource_type,
                alert.resource_name,
                str(exc),
            )
            continue
        except Exception:
            logger.exception(
                "dispatch_failed alert_key=%s resource_type=%s resource_name=%s",
                alert.alert_key,
                alert.resource_type,
                alert.resource_name,
            )
            continue
        if response is None:
            # dispatcher already logs the specific reason (skip_by_design / next_candidate / unknown)
            continue

        enrichment = _maybe_enrich_target_group_response(
            alert=alert,
            response=response,
            kubernetes_adapter=kubernetes_adapter,
            allowed_namespaces=list(config.allowed_namespaces or []),
        )
        if enrichment is not None:
            response.enrichment = enrichment

        # Record only after a successful dispatch to avoid poisoning cooldown
        pipeline.record_investigation(alert)

        analysis_result = None
        if config.assist_mode == "visible" and assist_service is not None:
            try:
                analysis_result = assist_service.after_investigation(
                    alert,
                    response,
                    channel=event["channel"],
                    thread_ts=reply_ts,
                )
            except Exception:
                logger.exception(
                    "assist_visible_failed alert_key=%s resource_type=%s",
                    alert.alert_key,
                    alert.resource_type,
                )

        client.chat_postMessage(  # type: ignore[union-attr]
            channel=event["channel"],
            thread_ts=reply_ts,
            text=format_investigation_reply(
                alert,
                response,
                analysis=_analysis_payload(analysis_result) if analysis_result is not None else None,
            ),
        )
        health_state, attention_required, resource_exists, primary_reason = _metadata_log_fields(
            response
        )
        logger.info(
            "investigation_replied alert_key=%s resource_type=%s channel=%s thread_ts=%s "
            "health_state=%s attention_required=%s resource_exists=%s primary_reason=%s",
            alert.alert_key,
            alert.resource_type,
            event["channel"],
            reply_ts,
            health_state,
            str(attention_required).lower(),
            str(resource_exists).lower(),
            primary_reason,
        )
        if config.assist_mode != "visible" and assist_service is not None:
            try:
                assist_service.after_investigation(
                    alert,
                    response,
                    channel=event["channel"],
                    thread_ts=reply_ts,
                )
            except Exception:
                logger.exception(
                    "assist_shadow_failed alert_key=%s resource_type=%s",
                    alert.alert_key,
                    alert.resource_type,
                )


def _maybe_enrich_target_group_response(
    *,
    alert: NormalizedAlertEvent,
    response: object,
    kubernetes_adapter: object | None,
    allowed_namespaces: list[str],
) -> dict[str, str] | None:
    if alert.resource_type != "target_group":
        return None
    if str(getattr(response, "result_state", "")).lower() != "success":
        return None

    actions_attempted = getattr(response, "actions_attempted", []) or []
    if actions_attempted != ["get_target_group_status"]:
        return None

    try:
        return enrich_target_group_response(
            alert=alert,
            response=response,
            kubernetes_adapter=kubernetes_adapter,
            allowed_namespaces=allowed_namespaces,
        )
    except Exception:
        logger.exception(
            "target_group_enrichment_failed alert_key=%s resource_name=%s",
            alert.alert_key,
            alert.resource_name,
        )
        return None
