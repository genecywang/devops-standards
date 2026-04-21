from __future__ import annotations

import logging
from dataclasses import fields, is_dataclass
from typing import Protocol

from alert_auto_investigator.assist.contracts import (
    AssistInvocationResult,
    AnalysisRequestPayload,
    AnalysisResponsePayload,
)
from alert_auto_investigator.assist.anthropic_backend import (
    AnthropicReadonlyAssistBackend,
    build_anthropic_client,
)
from alert_auto_investigator.assist.errors import AnalysisSchemaError
from alert_auto_investigator.assist.stub_backend import StubReadonlyAssistBackend
from alert_auto_investigator.assist.validators import ensure_analysis_payload_allowed
from alert_auto_investigator.config import InvestigatorConfig
from alert_auto_investigator.models.normalized_alert_event import NormalizedAlertEvent

logger = logging.getLogger(__name__)


class ReadonlyAssistBackend(Protocol):
    def generate(self, payload: AnalysisRequestPayload) -> AnalysisResponsePayload: ...


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
    ) -> AssistInvocationResult | None:
        if self._mode not in {"shadow", "visible"}:
            return

        payload = _build_payload(
            alert,
            response,
            channel=channel,
            thread_ts=thread_ts,
            analysis_mode=self._mode,
        )
        ensure_analysis_payload_allowed(
            bool(getattr(response, "redaction_applied", False)),
            {
                "alert": payload.alert,
                "investigation": payload.investigation,
                "context": payload.context,
                "prompt_version": payload.prompt_version,
                "output_schema_version": payload.output_schema_version,
                "analysis_mode": payload.analysis_mode,
                "max_input_tokens": payload.max_input_tokens,
                "max_output_tokens": payload.max_output_tokens,
            },
            max_input_chars=4000,
        )
        logger.info(
            "assist_shadow_invoked alert_key=%s resource_type=%s channel=%s thread_ts=%s",
            alert.alert_key,
            alert.resource_type,
            channel,
            thread_ts,
        )
        result = _coerce_response(self._backend.generate(payload))
        logger.info(
            "assist_shadow_completed alert_key=%s resource_type=%s confidence=%s",
            alert.alert_key,
            alert.resource_type,
            result.confidence or "unknown",
        )
        return AssistInvocationResult(request=payload, response=result)


def build_readonly_assist_service(config: InvestigatorConfig) -> ReadonlyAssistService:
    if config.assist_provider == "anthropic":
        backend = AnthropicReadonlyAssistBackend(
            client=build_anthropic_client(),
            model=config.assist_model,
            timeout_seconds=config.assist_timeout_seconds,
        )
    else:
        backend = StubReadonlyAssistBackend()

    return ReadonlyAssistService(
        mode=config.assist_mode,
        backend=backend,
    )


def _build_payload(
    alert: NormalizedAlertEvent,
    response: object,
    *,
    channel: str,
    thread_ts: str,
    analysis_mode: str,
) -> AnalysisRequestPayload:
    metadata = getattr(response, "metadata", {}) or {}
    actions_attempted = getattr(response, "actions_attempted", []) or []

    return AnalysisRequestPayload(
        alert={
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
        investigation={
            "result_state": str(getattr(response, "result_state", "unknown")).lower(),
            "check": actions_attempted[0] if actions_attempted else "none",
            "summary": str(getattr(response, "summary", "")),
            "metadata": metadata,
        },
        context={
            "channel": channel,
            "thread_ts": thread_ts,
        },
        prompt_version="analysis-v1",
        output_schema_version="v1",
        analysis_mode=analysis_mode,
        max_input_tokens=4000,
        max_output_tokens=500,
    )


def _coerce_response(result: object) -> AnalysisResponsePayload:
    if isinstance(result, AnalysisResponsePayload):
        return result
    if is_dataclass(result):
        data = {field.name: getattr(result, field.name) for field in fields(result)}
        try:
            return AnalysisResponsePayload(**data)
        except (TypeError, ValueError) as exc:
            raise AnalysisSchemaError(str(exc)) from exc
    if isinstance(result, dict):
        try:
            return AnalysisResponsePayload(**result)
        except (TypeError, ValueError) as exc:
            raise AnalysisSchemaError("missing required analysis response fields") from exc
    raise AnalysisSchemaError(
        f"unsupported analysis response type: {type(result).__name__}"
    )
