from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any

from alert_auto_investigator.assist.contracts import (
    ANALYSIS_RESULT_SUCCESS,
    AnalysisRequestPayload,
    AnalysisResponsePayload,
    AnalysisUsagePayload,
)
from alert_auto_investigator.assist.errors import (
    AnalysisProviderError,
    AnalysisSchemaError,
    AnalysisTimeoutError,
)


class AnthropicReadonlyAssistBackend:
    def __init__(self, client: Any, model: str, timeout_seconds: float) -> None:
        self._client = client
        self._model = model
        self._timeout_seconds = timeout_seconds

    def generate(self, payload: AnalysisRequestPayload) -> AnalysisResponsePayload:
        started_at = time.monotonic()
        try:
            message = self._client.messages.create(
                model=self._model,
                max_tokens=payload.max_output_tokens,
                temperature=0,
                timeout=self._timeout_seconds,
                system="You are a readonly incident analysis assistant.",
                messages=[
                    {
                        "role": "user",
                        "content": json.dumps(asdict(payload), ensure_ascii=True),
                    }
                ],
            )
        except TimeoutError as exc:
            raise AnalysisTimeoutError("analysis provider timed out") from exc
        except Exception as exc:
            raise AnalysisProviderError("analysis provider failed") from exc

        parsed = _parse_response_json(message)
        usage = getattr(message, "usage", None)
        latency_ms = int((time.monotonic() - started_at) * 1000)

        try:
            caveats = _coerce_caveats(parsed.get("caveats", []))
            return AnalysisResponsePayload(
                summary=str(parsed["summary"]),
                current_interpretation=str(parsed["current_interpretation"]),
                recommended_next_step=str(parsed["recommended_next_step"]),
                confidence=str(parsed["confidence"]),
                caveats=caveats,
                provider="anthropic",
                model=str(getattr(message, "model", self._model)),
                prompt_version=payload.prompt_version,
                output_schema_version=payload.output_schema_version,
                usage=AnalysisUsagePayload(
                    input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
                    output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
                    latency_ms=latency_ms,
                ),
                result_state=ANALYSIS_RESULT_SUCCESS,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AnalysisSchemaError("analysis provider returned invalid schema") from exc


def build_anthropic_client() -> Any:
    try:
        from anthropic import Anthropic
    except ImportError as exc:  # pragma: no cover - exercised only when SDK is absent
        raise ImportError(
            "anthropic package is required when OPENCLAW_READONLY_ASSIST_PROVIDER=anthropic"
        ) from exc

    return Anthropic()


def _parse_response_json(message: object) -> dict[str, Any]:
    content = getattr(message, "content", None)
    if not isinstance(content, list) or not content:
        raise AnalysisSchemaError("analysis provider returned empty content")

    text_blocks: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text")
        if isinstance(text, str):
            text_blocks.append(text)

    if not text_blocks:
        raise AnalysisSchemaError("analysis provider returned no text blocks")

    try:
        parsed = json.loads("".join(text_blocks))
    except (TypeError, json.JSONDecodeError) as exc:
        raise AnalysisSchemaError("analysis provider returned invalid JSON") from exc

    if not isinstance(parsed, dict):
        raise AnalysisSchemaError("analysis provider returned non-object JSON")

    return parsed


def _coerce_caveats(caveats: object) -> list[str]:
    if caveats is None:
        return []
    if not isinstance(caveats, (list, tuple)):
        raise AnalysisSchemaError("analysis provider returned invalid caveats")
    return [str(item) for item in caveats]
