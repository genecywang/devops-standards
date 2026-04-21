from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from alert_auto_investigator.assist.anthropic_backend import AnthropicReadonlyAssistBackend
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


def _make_request() -> AnalysisRequestPayload:
    return AnalysisRequestPayload(
        alert={"alert_key": "alert-1"},
        investigation={"result_state": "success"},
        context={"channel": "C123", "thread_ts": "111.000"},
        prompt_version="analysis-v1",
        output_schema_version="v1",
        analysis_mode="shadow",
        max_input_tokens=4000,
        max_output_tokens=500,
    )


def test_generate_maps_json_response_to_analysis_payload() -> None:
    client = Mock()
    client.messages.create.return_value = Mock(
        model="claude-3-7-sonnet",
        usage=Mock(input_tokens=210, output_tokens=120),
        content=[
            Mock(
                text=json.dumps(
                    {
                        "summary": "healthy",
                        "current_interpretation": "no infrastructure issue visible",
                        "recommended_next_step": "check metric trend",
                        "confidence": "medium",
                        "caveats": ["current-state only"],
                    }
                )
            )
        ],
    )
    backend = AnthropicReadonlyAssistBackend(
        client=client,
        model="claude-3-7-sonnet",
        timeout_seconds=10,
    )

    result = backend.generate(_make_request())

    assert result.provider == "anthropic"
    assert result.model == "claude-3-7-sonnet"
    assert result.summary == "healthy"
    assert result.current_interpretation == "no infrastructure issue visible"
    assert result.recommended_next_step == "check metric trend"
    assert result.confidence == "medium"
    assert result.caveats == ["current-state only"]
    assert result.usage == AnalysisUsagePayload(
        input_tokens=210,
        output_tokens=120,
        latency_ms=result.usage.latency_ms,
    )
    assert result.result_state == ANALYSIS_RESULT_SUCCESS

    client.messages.create.assert_called_once()
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-3-7-sonnet"
    assert kwargs["max_tokens"] == 500
    assert kwargs["timeout"] == 10
    assert kwargs["temperature"] == 0


def test_generate_maps_timeout_error() -> None:
    client = Mock()
    client.messages.create.side_effect = TimeoutError("boom")
    backend = AnthropicReadonlyAssistBackend(
        client=client,
        model="claude-3-7-sonnet",
        timeout_seconds=10,
    )

    with pytest.raises(AnalysisTimeoutError):
        backend.generate(_make_request())


def test_generate_maps_provider_error() -> None:
    client = Mock()
    client.messages.create.side_effect = RuntimeError("boom")
    backend = AnthropicReadonlyAssistBackend(
        client=client,
        model="claude-3-7-sonnet",
        timeout_seconds=10,
    )

    with pytest.raises(AnalysisProviderError):
        backend.generate(_make_request())


def test_generate_maps_invalid_json_to_schema_error() -> None:
    client = Mock()
    client.messages.create.return_value = Mock(
        model="claude-3-7-sonnet",
        usage=Mock(input_tokens=1, output_tokens=1),
        content=[Mock(text="{not-json}")],
    )
    backend = AnthropicReadonlyAssistBackend(
        client=client,
        model="claude-3-7-sonnet",
        timeout_seconds=10,
    )

    with pytest.raises(AnalysisSchemaError):
        backend.generate(_make_request())
