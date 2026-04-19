from __future__ import annotations

import logging
from typing import Protocol

from alert_auto_investigator.assist.stub_backend import StubReadonlyAssistBackend
from alert_auto_investigator.config import InvestigatorConfig
from alert_auto_investigator.models.normalized_alert_event import NormalizedAlertEvent

logger = logging.getLogger(__name__)


class ReadonlyAssistBackend(Protocol):
    def generate(self, payload: dict[str, object]) -> dict[str, object]: ...


class ReadonlyAssistService:
    def __init__(self, mode: str, backend: ReadonlyAssistBackend) -> None:
        self._mode = mode
        self._backend = backend

    def after_investigation(
        self,
        alert: NormalizedAlertEvent,
        response: object,
        *,
        channel: str,
        thread_ts: str,
    ) -> None:
        if self._mode != "shadow":
            return

        payload = _build_payload(alert, response, channel=channel, thread_ts=thread_ts)
        logger.info(
            "assist_shadow_invoked alert_key=%s resource_type=%s channel=%s thread_ts=%s",
            alert.alert_key,
            alert.resource_type,
            channel,
            thread_ts,
        )
        result = self._backend.generate(payload)
        logger.info(
            "assist_shadow_completed alert_key=%s resource_type=%s confidence=%s",
            alert.alert_key,
            alert.resource_type,
            str(result.get("confidence") or "unknown"),
        )


def build_readonly_assist_service(config: InvestigatorConfig) -> ReadonlyAssistService:
    return ReadonlyAssistService(
        mode=config.assist_mode,
        backend=StubReadonlyAssistBackend(),
    )


def _build_payload(
    alert: NormalizedAlertEvent,
    response: object,
    *,
    channel: str,
    thread_ts: str,
) -> dict[str, object]:
    metadata = getattr(response, "metadata", {}) or {}
    actions_attempted = getattr(response, "actions_attempted", []) or []

    return {
        "alert": {
            "source": alert.source,
            "alert_name": alert.alert_name,
            "alert_key": alert.alert_key,
            "environment": alert.environment,
            "cluster": alert.cluster,
            "namespace": alert.namespace,
            "resource_type": alert.resource_type,
            "resource_name": alert.resource_name,
            "summary": alert.summary,
        },
        "investigation": {
            "result_state": str(getattr(response, "result_state", "unknown")).lower(),
            "check": actions_attempted[0] if actions_attempted else "none",
            "summary": str(getattr(response, "summary", "")),
            "metadata": metadata,
        },
        "context": {
            "channel": channel,
            "thread_ts": thread_ts,
        },
    }
