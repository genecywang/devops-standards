# Alert Investigation Analysis Layer MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing readonly assist hook into a bounded, provider-neutral analysis layer that can run in `off`, `shadow`, and `visible` modes without breaking deterministic investigation replies.

**Architecture:** Keep `alert_auto_investigator` as the product integration layer and evolve the existing `assist/` package rather than introducing a second parallel service. Build a provider-neutral backend contract, add analysis-specific audit + validation, then wire in one real provider adapter (`Anthropic`) behind the backend protocol while preserving fail-open behavior.

**Tech Stack:** Python 3.11, pytest, existing `alert_auto_investigator` assist hook, existing `openclaw_foundation` redaction utilities, Anthropic Python SDK

---

## File Map

### Modify

- `alert_auto_investigator/src/alert_auto_investigator/assist/service.py`
  - evolve payload contract
  - support `shadow` and `visible`
  - add structured result handling
- `alert_auto_investigator/src/alert_auto_investigator/assist/stub_backend.py`
  - return the new structured analysis shape
- `alert_auto_investigator/src/alert_auto_investigator/config.py`
  - keep `OPENCLAW_READONLY_ASSIST_MODE`
  - add analysis provider settings and budgets
- `alert_auto_investigator/src/alert_auto_investigator/service/handler.py`
  - append visible analysis output to Slack reply
  - keep fail-open behavior
- `alert_auto_investigator/src/alert_auto_investigator/service/formatter.py`
  - render analysis section with AI disclaimer
- `alert_auto_investigator/tests/test_handler.py`
  - cover `off` / `shadow` / `visible`
  - cover fail-open for provider / schema / redaction failures
- `alert_auto_investigator/tests/test_formatter.py`
  - cover analysis section rendering and disclaimer
- `deploy/charts/alert-auto-investigator/values.yaml`
  - add analysis config defaults
- `deploy/charts/alert-auto-investigator/templates/configmap.yaml`
  - project analysis config env vars
- `alert_auto_investigator/docs/aws-operations.md`
  - document shadow / visible verification and rollback

### Create

- `alert_auto_investigator/src/alert_auto_investigator/assist/contracts.py`
  - request / response / usage dataclasses
  - result-state enum/constants
- `alert_auto_investigator/src/alert_auto_investigator/assist/errors.py`
  - analysis error types
- `alert_auto_investigator/src/alert_auto_investigator/assist/audit.py`
  - analysis-specific audit event dataclass + digest helper
- `alert_auto_investigator/src/alert_auto_investigator/assist/validators.py`
  - input redaction gate
  - token / size ceiling helpers
- `alert_auto_investigator/src/alert_auto_investigator/assist/anthropic_backend.py`
  - first real provider adapter
- `alert_auto_investigator/tests/test_assist_service.py`
  - payload building, mode handling, analysis result-state mapping
- `alert_auto_investigator/tests/test_assist_audit.py`
  - audit event shape and digest behavior
- `alert_auto_investigator/tests/test_assist_validators.py`
  - redaction gate and budget limit tests
- `alert_auto_investigator/tests/test_anthropic_backend.py`
  - provider adapter contract mapping

---

### Task 1: Define Analysis Contract On Top Of Existing Assist Flow

**Files:**
- Create: `alert_auto_investigator/src/alert_auto_investigator/assist/contracts.py`
- Create: `alert_auto_investigator/src/alert_auto_investigator/assist/errors.py`
- Modify: `alert_auto_investigator/src/alert_auto_investigator/assist/service.py`
- Modify: `alert_auto_investigator/src/alert_auto_investigator/assist/stub_backend.py`
- Test: `alert_auto_investigator/tests/test_assist_service.py`

- [ ] **Step 1: Write failing tests for the structured assist contract**

```python
from alert_auto_investigator.assist.contracts import (
    AnalysisRequestPayload,
    AnalysisResponsePayload,
    AnalysisUsagePayload,
)
from alert_auto_investigator.assist.errors import AnalysisSchemaError
from alert_auto_investigator.assist.service import ReadonlyAssistService


class _BackendStub:
    def __init__(self, result):
        self._result = result
        self.last_payload = None

    def generate(self, payload):
        self.last_payload = payload
        return self._result


def test_after_investigation_builds_structured_payload() -> None:
    backend = _BackendStub(
        AnalysisResponsePayload(
            summary="current state is healthy",
            current_interpretation="no infrastructure-side degradation is visible",
            recommended_next_step="check CloudWatch metric trend before escalating",
            confidence="medium",
            caveats=["only current state was inspected"],
            provider="stub",
            model="stub-v1",
            prompt_version="analysis-v1",
            output_schema_version="v1",
            usage=AnalysisUsagePayload(input_tokens=120, output_tokens=80, latency_ms=10),
            result_state="success",
        )
    )
    service = ReadonlyAssistService(mode="shadow", backend=backend)

    result = service.after_investigation(
        make_alert(),
        make_response(),
        channel="C123",
        thread_ts="111.222",
    )

    assert result is not None
    assert isinstance(result.request, AnalysisRequestPayload)
    assert backend.last_payload["alert"]["alert_key"] == make_alert().alert_key
    assert backend.last_payload["investigation"]["summary"] == make_response().summary


def test_after_investigation_rejects_backend_dict_without_required_fields() -> None:
    backend = _BackendStub({"confidence": "low"})
    service = ReadonlyAssistService(mode="shadow", backend=backend)

    with pytest.raises(AnalysisSchemaError, match="summary is required"):
        service.after_investigation(
            make_alert(),
            make_response(),
            channel="C123",
            thread_ts="111.222",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest alert_auto_investigator/tests/test_assist_service.py -v
```

Expected:

- FAIL because structured contract classes do not exist yet
- FAIL because `ReadonlyAssistService.after_investigation()` currently returns `None`

- [ ] **Step 3: Add the contract dataclasses and result-state constants**

```python
from __future__ import annotations

from dataclasses import dataclass, field


ANALYSIS_RESULT_SUCCESS = "success"
ANALYSIS_RESULT_SCHEMA_ERROR = "schema_error"
ANALYSIS_RESULT_TIMEOUT = "timeout"
ANALYSIS_RESULT_RATE_LIMIT = "rate_limit"
ANALYSIS_RESULT_PROVIDER_ERROR = "provider_error"
ANALYSIS_RESULT_REDACTION_BLOCKED = "redaction_blocked"


@dataclass(slots=True)
class AnalysisUsagePayload:
    input_tokens: int
    output_tokens: int
    latency_ms: int


@dataclass(slots=True)
class AnalysisRequestPayload:
    alert: dict[str, object]
    investigation: dict[str, object]
    context: dict[str, object]
    prompt_version: str
    output_schema_version: str
    analysis_mode: str
    max_input_tokens: int
    max_output_tokens: int


@dataclass(slots=True)
class AnalysisResponsePayload:
    summary: str
    current_interpretation: str
    recommended_next_step: str
    confidence: str
    caveats: list[str] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    prompt_version: str = "analysis-v1"
    output_schema_version: str = "v1"
    usage: AnalysisUsagePayload | None = None
    result_state: str = ANALYSIS_RESULT_SUCCESS

    def __post_init__(self) -> None:
        if not self.summary:
            raise ValueError("summary is required")
        if not self.current_interpretation:
            raise ValueError("current_interpretation is required")
        if not self.recommended_next_step:
            raise ValueError("recommended_next_step is required")
        if not self.confidence:
            raise ValueError("confidence is required")
```

- [ ] **Step 4: Add assist error types**

```python
class AnalysisError(Exception):
    pass


class AnalysisTimeoutError(AnalysisError):
    pass


class AnalysisRateLimitError(AnalysisError):
    pass


class AnalysisProviderError(AnalysisError):
    pass


class AnalysisSchemaError(AnalysisError):
    pass


class AnalysisRedactionBlockedError(AnalysisError):
    pass
```

- [ ] **Step 5: Evolve `ReadonlyAssistService` to return a structured result**

```python
@dataclass(slots=True)
class AssistInvocationResult:
    request: AnalysisRequestPayload
    response: AnalysisResponsePayload


class ReadonlyAssistBackend(Protocol):
    def generate(self, payload: AnalysisRequestPayload) -> AnalysisResponsePayload: ...


def after_investigation(... ) -> AssistInvocationResult | None:
    if self._mode == "off":
        return None

    payload = _build_payload(...)
    result = self._backend.generate(payload)
    return AssistInvocationResult(request=payload, response=result)
```

- [ ] **Step 6: Update the stub backend to emit the new shape**

```python
from alert_auto_investigator.assist.contracts import (
    ANALYSIS_RESULT_SUCCESS,
    AnalysisResponsePayload,
    AnalysisUsagePayload,
)


class StubReadonlyAssistBackend:
    def generate(self, payload):
        return AnalysisResponsePayload(
            summary="shadow-mode stub summary",
            current_interpretation="shadow-mode stub interpretation",
            recommended_next_step="no action; stub backend only",
            confidence="low",
            caveats=["stub backend"],
            provider="stub",
            model="stub-v1",
            prompt_version=payload.prompt_version,
            output_schema_version=payload.output_schema_version,
            usage=AnalysisUsagePayload(input_tokens=0, output_tokens=0, latency_ms=0),
            result_state=ANALYSIS_RESULT_SUCCESS,
        )
```

- [ ] **Step 7: Run tests to verify they pass**

Run:

```bash
pytest alert_auto_investigator/tests/test_assist_service.py -v
```

Expected:

- PASS

- [ ] **Step 8: Commit**

```bash
git add alert_auto_investigator/src/alert_auto_investigator/assist/contracts.py \
  alert_auto_investigator/src/alert_auto_investigator/assist/errors.py \
  alert_auto_investigator/src/alert_auto_investigator/assist/service.py \
  alert_auto_investigator/src/alert_auto_investigator/assist/stub_backend.py \
  alert_auto_investigator/tests/test_assist_service.py
git commit -m "feat(alert-auto-investigator): define readonly assist analysis contract"
```

---

### Task 2: Add Analysis Audit Event And Digest Rules

**Files:**
- Create: `alert_auto_investigator/src/alert_auto_investigator/assist/audit.py`
- Test: `alert_auto_investigator/tests/test_assist_audit.py`

- [ ] **Step 1: Write failing audit tests**

```python
from alert_auto_investigator.assist.audit import AnalysisAuditEvent, build_response_digest


def test_build_response_digest_hashes_redacted_canonical_json() -> None:
    digest = build_response_digest(
        {
            "summary": "healthy",
            "caveats": ["token=[REDACTED]"],
        }
    )

    assert len(digest) == 64
    assert digest != "healthy"


def test_analysis_audit_event_captures_required_fields() -> None:
    event = AnalysisAuditEvent(
        request_id="req-001",
        alert_key="cloudwatch_alarm:123:ap-east-2:test",
        resource_type="elasticache_cluster",
        resource_name="dev-redis-001",
        tool_name="get_elasticache_cluster_status",
        provider="anthropic",
        model="claude-sonnet",
        prompt_version="analysis-v1",
        analysis_mode="shadow",
        latency_ms=80,
        input_tokens=220,
        output_tokens=110,
        analysis_result_state="success",
        response_digest="a" * 64,
    )

    assert event.provider == "anthropic"
    assert event.analysis_result_state == "success"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest alert_auto_investigator/tests/test_assist_audit.py -v
```

Expected:

- FAIL because audit module does not exist yet

- [ ] **Step 3: Implement analysis-specific audit dataclass and digest helper**

```python
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


def build_response_digest(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class AnalysisAuditEvent:
    request_id: str
    alert_key: str
    resource_type: str
    resource_name: str
    tool_name: str
    provider: str
    model: str
    prompt_version: str
    analysis_mode: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    analysis_result_state: str
    response_digest: str
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest alert_auto_investigator/tests/test_assist_audit.py -v
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add alert_auto_investigator/src/alert_auto_investigator/assist/audit.py \
  alert_auto_investigator/tests/test_assist_audit.py
git commit -m "feat(alert-auto-investigator): add analysis audit contract"
```

---

### Task 3: Enforce Redaction And Provider Call Budget

**Files:**
- Create: `alert_auto_investigator/src/alert_auto_investigator/assist/validators.py`
- Modify: `alert_auto_investigator/src/alert_auto_investigator/assist/service.py`
- Test: `alert_auto_investigator/tests/test_assist_validators.py`
- Test: `alert_auto_investigator/tests/test_assist_service.py`

- [ ] **Step 1: Write failing tests for redaction gating and payload budget**

```python
from alert_auto_investigator.assist.errors import AnalysisRedactionBlockedError
from alert_auto_investigator.assist.validators import ensure_analysis_payload_allowed


def test_analysis_payload_rejects_unredacted_response() -> None:
    with pytest.raises(AnalysisRedactionBlockedError, match="redaction_applied must be true"):
        ensure_analysis_payload_allowed(
            response_redaction_applied=False,
            payload={"investigation": {"summary": "raw token=secret"}},
            max_input_chars=4000,
        )


def test_analysis_payload_rejects_oversized_payload() -> None:
    with pytest.raises(AnalysisRedactionBlockedError, match="analysis payload exceeds max input size"):
        ensure_analysis_payload_allowed(
            response_redaction_applied=True,
            payload={"investigation": {"summary": "x" * 5001}},
            max_input_chars=4000,
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest alert_auto_investigator/tests/test_assist_validators.py alert_auto_investigator/tests/test_assist_service.py -v
```

Expected:

- FAIL because validator module and enforcement do not exist yet

- [ ] **Step 3: Implement redaction gate and bounded payload size check**

```python
from __future__ import annotations

import json

from alert_auto_investigator.assist.errors import AnalysisRedactionBlockedError


def ensure_analysis_payload_allowed(
    *,
    response_redaction_applied: bool,
    payload: dict[str, object],
    max_input_chars: int,
) -> None:
    if not response_redaction_applied:
        raise AnalysisRedactionBlockedError("redaction_applied must be true")

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    if len(canonical) > max_input_chars:
        raise AnalysisRedactionBlockedError("analysis payload exceeds max input size")
```

- [ ] **Step 4: Call the validator from assist service before backend invocation**

```python
ensure_analysis_payload_allowed(
    response_redaction_applied=bool(getattr(response, "redaction_applied", False)),
    payload=payload,
    max_input_chars=self._max_input_chars,
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
pytest alert_auto_investigator/tests/test_assist_validators.py alert_auto_investigator/tests/test_assist_service.py -v
```

Expected:

- PASS

- [ ] **Step 6: Commit**

```bash
git add alert_auto_investigator/src/alert_auto_investigator/assist/validators.py \
  alert_auto_investigator/src/alert_auto_investigator/assist/service.py \
  alert_auto_investigator/tests/test_assist_validators.py \
  alert_auto_investigator/tests/test_assist_service.py
git commit -m "feat(alert-auto-investigator): gate assist analysis on redaction and budget"
```

---

### Task 4: Add Visible Mode And Slack Rendering

**Files:**
- Modify: `alert_auto_investigator/src/alert_auto_investigator/service/handler.py`
- Modify: `alert_auto_investigator/src/alert_auto_investigator/service/formatter.py`
- Modify: `alert_auto_investigator/src/alert_auto_investigator/config.py`
- Test: `alert_auto_investigator/tests/test_handler.py`
- Test: `alert_auto_investigator/tests/test_formatter.py`

- [ ] **Step 1: Write failing tests for visible mode reply behavior**

```python
def test_visible_assist_appends_ai_analysis_section() -> None:
    client = MagicMock()
    dispatcher = MagicMock()
    dispatcher.dispatch.return_value = make_response()
    assist_service = MagicMock()
    assist_service.after_investigation.return_value = make_assist_result()
    config = _make_config(assist_mode="visible")
    pipeline = _make_pipeline(config)

    handle_message(
        _make_event(attachments=[{"text": _ELASTICACHE_TEXT}], ts="111.000"),
        client,
        config,
        pipeline,
        dispatcher,
        assist_service=assist_service,
    )

    reply_text = client.chat_postMessage.call_args.kwargs["text"]
    assert "*AI Analysis*" in reply_text
    assert "AI-generated" in reply_text
    assert "verify before acting" in reply_text


def test_visible_assist_failure_keeps_primary_reply() -> None:
    client = MagicMock()
    dispatcher = MagicMock()
    dispatcher.dispatch.return_value = make_response()
    assist_service = MagicMock()
    assist_service.after_investigation.side_effect = RuntimeError("provider boom")
    config = _make_config(assist_mode="visible")
    pipeline = _make_pipeline(config)

    handle_message(
        _make_event(attachments=[{"text": _ELASTICACHE_TEXT}], ts="111.000"),
        client,
        config,
        pipeline,
        dispatcher,
        assist_service=assist_service,
    )

    reply_text = client.chat_postMessage.call_args.kwargs["text"]
    assert "*Investigation Result*" in reply_text
    assert "*AI Analysis*" not in reply_text
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest alert_auto_investigator/tests/test_handler.py alert_auto_investigator/tests/test_formatter.py -v
```

Expected:

- FAIL because formatter does not render analysis section yet
- FAIL because `visible` mode is not yet special-cased

- [ ] **Step 3: Extend config to accept visible mode and provider budgets**

```python
assist_mode=os.environ.get("OPENCLAW_READONLY_ASSIST_MODE", "off"),
assist_provider=os.environ.get("OPENCLAW_READONLY_ASSIST_PROVIDER", "stub"),
assist_prompt_version=os.environ.get("OPENCLAW_READONLY_ASSIST_PROMPT_VERSION", "analysis-v1"),
assist_output_schema_version=os.environ.get("OPENCLAW_READONLY_ASSIST_OUTPUT_SCHEMA_VERSION", "v1"),
assist_timeout_seconds=float(os.environ.get("OPENCLAW_READONLY_ASSIST_TIMEOUT_SECONDS", "10")),
assist_max_input_chars=int(os.environ.get("OPENCLAW_READONLY_ASSIST_MAX_INPUT_CHARS", "4000")),
assist_max_output_tokens=int(os.environ.get("OPENCLAW_READONLY_ASSIST_MAX_OUTPUT_TOKENS", "500")),
```

- [ ] **Step 4: Update formatter to append AI analysis section**

```python
def _format_analysis_lines(analysis: dict[str, object]) -> list[str]:
    if not analysis:
        return []

    summary = str(analysis.get("summary") or "").strip()
    interpretation = str(analysis.get("current_interpretation") or "").strip()
    next_step = str(analysis.get("recommended_next_step") or "").strip()
    confidence = str(analysis.get("confidence") or "").strip()
    caveats = analysis.get("caveats") or []
    if not summary or not interpretation or not next_step or not confidence:
        return []

    lines = [
        "*AI Analysis*",
        "_AI-generated; verify before acting_",
        f"*Confidence:* {confidence}",
        f"*AI Summary:* {summary}",
        f"*Interpretation:* {interpretation}",
        f"*Next Step:* {next_step}",
    ]
    if isinstance(caveats, list) and caveats:
        lines.append("*Caveats:* " + "; ".join(str(item) for item in caveats))
    return lines
```

- [ ] **Step 5: Attach visible analysis to the reply path in handler**

```python
assist_result = None
if assist_service is not None:
    assist_result = assist_service.after_investigation(...)

analysis_payload = {}
if config.assist_mode == "visible" and assist_result is not None:
    analysis_payload = {
        "summary": assist_result.response.summary,
        "current_interpretation": assist_result.response.current_interpretation,
        "recommended_next_step": assist_result.response.recommended_next_step,
        "confidence": assist_result.response.confidence,
        "caveats": assist_result.response.caveats,
    }

client.chat_postMessage(
    ...,
    text=format_investigation_reply(alert, response, analysis=analysis_payload),
)
```

- [ ] **Step 6: Run tests to verify they pass**

Run:

```bash
pytest alert_auto_investigator/tests/test_handler.py alert_auto_investigator/tests/test_formatter.py -v
```

Expected:

- PASS

- [ ] **Step 7: Commit**

```bash
git add alert_auto_investigator/src/alert_auto_investigator/config.py \
  alert_auto_investigator/src/alert_auto_investigator/service/handler.py \
  alert_auto_investigator/src/alert_auto_investigator/service/formatter.py \
  alert_auto_investigator/tests/test_handler.py \
  alert_auto_investigator/tests/test_formatter.py
git commit -m "feat(alert-auto-investigator): support visible readonly assist analysis"
```

---

### Task 5: Add Anthropic Backend Adapter

**Files:**
- Create: `alert_auto_investigator/src/alert_auto_investigator/assist/anthropic_backend.py`
- Modify: `alert_auto_investigator/src/alert_auto_investigator/assist/service.py`
- Test: `alert_auto_investigator/tests/test_anthropic_backend.py`

- [ ] **Step 1: Write failing Anthropic adapter tests**

```python
from alert_auto_investigator.assist.anthropic_backend import AnthropicReadonlyAssistBackend
from alert_auto_investigator.assist.contracts import AnalysisRequestPayload


def test_anthropic_backend_maps_json_response_to_analysis_payload() -> None:
    client = Mock()
    client.messages.create.return_value = Mock(
        model="claude-3-7-sonnet",
        usage=Mock(input_tokens=210, output_tokens=120),
        content=[Mock(text='{"summary":"healthy","current_interpretation":"no infrastructure issue visible","recommended_next_step":"check metric trend","confidence":"medium","caveats":["current-state only"]}')],
    )
    backend = AnthropicReadonlyAssistBackend(client=client, model="claude-3-7-sonnet", timeout_seconds=10)

    result = backend.generate(make_analysis_request())

    assert result.provider == "anthropic"
    assert result.model == "claude-3-7-sonnet"
    assert result.summary == "healthy"
    assert result.usage.input_tokens == 210


def test_anthropic_backend_maps_timeout_error() -> None:
    client = Mock()
    client.messages.create.side_effect = TimeoutError("boom")
    backend = AnthropicReadonlyAssistBackend(client=client, model="claude-3-7-sonnet", timeout_seconds=10)

    with pytest.raises(AnalysisTimeoutError):
        backend.generate(make_analysis_request())
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest alert_auto_investigator/tests/test_anthropic_backend.py -v
```

Expected:

- FAIL because Anthropic backend does not exist yet

- [ ] **Step 3: Implement Anthropic backend mapping**

```python
from __future__ import annotations

import json
import time

from alert_auto_investigator.assist.contracts import AnalysisResponsePayload, AnalysisUsagePayload
from alert_auto_investigator.assist.errors import (
    AnalysisProviderError,
    AnalysisRateLimitError,
    AnalysisSchemaError,
    AnalysisTimeoutError,
)


class AnthropicReadonlyAssistBackend:
    def __init__(self, client, model: str, timeout_seconds: float) -> None:
        self._client = client
        self._model = model
        self._timeout_seconds = timeout_seconds

    def generate(self, payload):
        started = time.monotonic()
        try:
            message = self._client.messages.create(
                model=self._model,
                max_tokens=payload.max_output_tokens,
                temperature=0,
                system="You are a readonly incident analysis assistant.",
                messages=[{"role": "user", "content": json.dumps(payload.__dict__, ensure_ascii=True)}],
            )
        except TimeoutError as error:
            raise AnalysisTimeoutError("analysis provider timed out") from error
        except Exception as error:
            raise AnalysisProviderError("analysis provider failed") from error

        try:
            parsed = json.loads(message.content[0].text)
        except Exception as error:
            raise AnalysisSchemaError("analysis provider returned invalid JSON") from error

        latency_ms = int((time.monotonic() - started) * 1000)
        return AnalysisResponsePayload(
            summary=str(parsed["summary"]),
            current_interpretation=str(parsed["current_interpretation"]),
            recommended_next_step=str(parsed["recommended_next_step"]),
            confidence=str(parsed["confidence"]),
            caveats=[str(item) for item in parsed.get("caveats", [])],
            provider="anthropic",
            model=str(getattr(message, "model", self._model)),
            prompt_version=payload.prompt_version,
            output_schema_version=payload.output_schema_version,
            usage=AnalysisUsagePayload(
                input_tokens=int(getattr(message.usage, "input_tokens", 0)),
                output_tokens=int(getattr(message.usage, "output_tokens", 0)),
                latency_ms=latency_ms,
            ),
            result_state="success",
        )
```

- [ ] **Step 4: Wire backend construction into `build_readonly_assist_service()`**

```python
if config.assist_provider == "anthropic":
    backend = AnthropicReadonlyAssistBackend(
        client=build_anthropic_client(),
        model=config.assist_model,
        timeout_seconds=config.assist_timeout_seconds,
    )
else:
    backend = StubReadonlyAssistBackend()
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
pytest alert_auto_investigator/tests/test_anthropic_backend.py alert_auto_investigator/tests/test_assist_service.py -v
```

Expected:

- PASS

- [ ] **Step 6: Commit**

```bash
git add alert_auto_investigator/src/alert_auto_investigator/assist/anthropic_backend.py \
  alert_auto_investigator/src/alert_auto_investigator/assist/service.py \
  alert_auto_investigator/tests/test_anthropic_backend.py \
  alert_auto_investigator/tests/test_assist_service.py
git commit -m "feat(alert-auto-investigator): add anthropic readonly assist backend"
```

---

### Task 6: Add Config, Helm Wiring, And Operations Notes

**Files:**
- Modify: `deploy/charts/alert-auto-investigator/values.yaml`
- Modify: `deploy/charts/alert-auto-investigator/templates/configmap.yaml`
- Modify: `alert_auto_investigator/docs/aws-operations.md`

- [ ] **Step 1: Write the expected config defaults into the chart values**

```yaml
analysis:
  mode: off
  provider: stub
  model: claude-3-7-sonnet
  promptVersion: analysis-v1
  outputSchemaVersion: v1
  timeoutSeconds: "10"
  maxInputChars: "4000"
  maxOutputTokens: "500"
```

- [ ] **Step 2: Project analysis env vars from Helm configmap**

```yaml
  OPENCLAW_READONLY_ASSIST_MODE: {{ .Values.analysis.mode | quote }}
  OPENCLAW_READONLY_ASSIST_PROVIDER: {{ .Values.analysis.provider | quote }}
  OPENCLAW_READONLY_ASSIST_MODEL: {{ .Values.analysis.model | quote }}
  OPENCLAW_READONLY_ASSIST_PROMPT_VERSION: {{ .Values.analysis.promptVersion | quote }}
  OPENCLAW_READONLY_ASSIST_OUTPUT_SCHEMA_VERSION: {{ .Values.analysis.outputSchemaVersion | quote }}
  OPENCLAW_READONLY_ASSIST_TIMEOUT_SECONDS: {{ .Values.analysis.timeoutSeconds | quote }}
  OPENCLAW_READONLY_ASSIST_MAX_INPUT_CHARS: {{ .Values.analysis.maxInputChars | quote }}
  OPENCLAW_READONLY_ASSIST_MAX_OUTPUT_TOKENS: {{ .Values.analysis.maxOutputTokens | quote }}
```

- [ ] **Step 3: Document shadow / visible rollout and rollback**

```md
### Readonly Assist Analysis Rollout

Recommended rollout:

1. `off`
2. `shadow`
3. `visible`

Shadow verification:

- look for `assist_shadow_invoked`
- look for analysis audit event with `analysis_result_state=success`
- confirm Slack reply remains deterministic-only

Visible verification:

- confirm Slack reply contains `*AI Analysis*`
- confirm section includes `AI-generated` and `verify before acting`
- confirm provider failure still preserves deterministic reply

Rollback:

- set `OPENCLAW_READONLY_ASSIST_MODE=off`
- redeploy chart
```

- [ ] **Step 4: Run Helm template to verify the config renders**

Run:

```bash
helm template alert-auto-investigator ./deploy/charts/alert-auto-investigator -n devops
```

Expected:

- PASS
- configmap includes `OPENCLAW_READONLY_ASSIST_*` env vars

- [ ] **Step 5: Commit**

```bash
git add deploy/charts/alert-auto-investigator/values.yaml \
  deploy/charts/alert-auto-investigator/templates/configmap.yaml \
  alert_auto_investigator/docs/aws-operations.md
git commit -m "docs(alert-auto-investigator): document readonly assist rollout"
```

---

### Task 7: Run Focused Verification And Regression

**Files:**
- Test only

- [ ] **Step 1: Run focused assist and formatter coverage**

Run:

```bash
pytest alert_auto_investigator/tests/test_assist_service.py \
  alert_auto_investigator/tests/test_assist_audit.py \
  alert_auto_investigator/tests/test_assist_validators.py \
  alert_auto_investigator/tests/test_anthropic_backend.py \
  alert_auto_investigator/tests/test_handler.py \
  alert_auto_investigator/tests/test_formatter.py -v
```

Expected:

- PASS

- [ ] **Step 2: Run adjacent investigation regression**

Run:

```bash
pytest alert_auto_investigator/tests/test_golden_replays.py \
  alert_auto_investigator/tests/test_runner_factory.py \
  openclaw_foundation/tests/test_aws_elasticache_cluster_status_tool.py \
  openclaw_foundation/tests/test_aws_adapter.py -v
```

Expected:

- PASS

- [ ] **Step 3: Commit final fixes if verification required follow-up changes**

```bash
git status --short
```

Expected:

- no changes, or only intentional follow-up fixes

If follow-up changes were needed:

```bash
git add <files>
git commit -m "test(alert-auto-investigator): stabilize readonly assist analysis mvp"
```

---

## Plan Review

This plan covers:

- existing assist hook evolution instead of parallel service creation
- structured contract and result-state enum
- analysis-specific audit event placement
- redaction and budget gates
- shadow / visible compatibility
- one real provider adapter (`Anthropic`)
- rollout / verification notes

No task in this plan implements:

- agent loop
- second real provider adapter
- foundation audit debt cleanup
- spend enforcement

