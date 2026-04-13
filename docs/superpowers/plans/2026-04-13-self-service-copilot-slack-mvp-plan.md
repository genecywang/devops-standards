# Self-Service Ops Copilot — Slack MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Slack Socket Mode bot in a new `self_service_copilot/` package that dispatches @mention commands to `openclaw_foundation`'s `OpenClawRunner` and replies to the Slack thread.

**Architecture:** `@copilot <tool_name> <namespace> <resource_name>` mention → `parser.py` → `ParsedCommand` → `dispatcher.py` → `InvestigationRequest` → `OpenClawRunner` → `CanonicalResponse` → `formatter.py` → Slack thread reply. All allowlist policy enforced in dispatcher before runner. Foundation model gets one backward-compatible field addition (`requested_by`).

**Tech Stack:** Python 3.11+, `slack-bolt>=1.18` (Socket Mode), `openclaw-foundation` (local), `pytest`

---

## File Map

| Operation | Path | Responsibility |
|---|---|---|
| Modify | `openclaw_foundation/src/openclaw_foundation/models/requests.py` | Add `requested_by: str \| None = None` |
| Modify | `openclaw_foundation/tests/test_models.py` | Add test for `requested_by` field |
| Create | `self_service_copilot/pyproject.toml` | Package config, deps |
| Create | `self_service_copilot/src/self_service_copilot/__init__.py` | Empty |
| Create | `self_service_copilot/src/self_service_copilot/config.py` | `CopilotConfig` dataclass + `from_env()` |
| Create | `self_service_copilot/src/self_service_copilot/parser.py` | `ParsedCommand`, `ParseError`, `UnknownCommandError`, `UsageError`, `parse()` |
| Create | `self_service_copilot/src/self_service_copilot/dispatcher.py` | `SlackContext`, `DispatchError`, `make_request_id()`, `build_request()` |
| Create | `self_service_copilot/src/self_service_copilot/formatter.py` | `format_response()`, `format_parse_error()`, `format_dispatch_error()` |
| Create | `self_service_copilot/src/self_service_copilot/bot.py` | Slack `App` + `SocketModeHandler` + `main()` |
| Create | `self_service_copilot/tests/__init__.py` | Empty |
| Create | `self_service_copilot/tests/test_parser.py` | Parser unit tests |
| Create | `self_service_copilot/tests/test_dispatcher.py` | Dispatcher unit tests |
| Create | `self_service_copilot/tests/test_formatter.py` | Formatter unit tests |

---

## Task 0: Add `requested_by` to `InvestigationRequest`

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/models/requests.py`
- Modify: `openclaw_foundation/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

In `openclaw_foundation/tests/test_models.py`, add after the existing tests:

```python
def test_investigation_request_accepts_optional_requested_by() -> None:
    from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
    from openclaw_foundation.models.enums import RequestType

    request = InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-001",
        source_product="self_service_copilot",
        scope={"environment": "staging"},
        input_ref="slack://C001/123",
        budget=ExecutionBudget(max_steps=2, max_tool_calls=1, max_duration_seconds=15, max_output_tokens=512),
        requested_by="U999",
    )

    assert request.requested_by == "U999"


def test_investigation_request_requested_by_defaults_to_none() -> None:
    from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
    from openclaw_foundation.models.enums import RequestType

    request = InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-001",
        source_product="cli",
        scope={"environment": "staging"},
        input_ref="fixture:x",
        budget=ExecutionBudget(max_steps=2, max_tool_calls=1, max_duration_seconds=15, max_output_tokens=512),
    )

    assert request.requested_by is None
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd openclaw_foundation && .venv/bin/pytest tests/test_models.py::test_investigation_request_accepts_optional_requested_by -v
```

Expected: `FAILED` — `TypeError: unexpected keyword argument 'requested_by'`

- [ ] **Step 3: Add the field to `InvestigationRequest`**

In `openclaw_foundation/src/openclaw_foundation/models/requests.py`, add `requested_by` after `target`:

```python
@dataclass(slots=True)
class InvestigationRequest:
    request_type: RequestType
    request_id: str
    source_product: str
    scope: dict[str, str]
    input_ref: str
    budget: ExecutionBudget
    tool_name: str = "fake_investigation"
    target: dict[str, str] | None = None
    requested_by: str | None = None
```

- [ ] **Step 4: Run to verify both new tests pass and no regressions**

```bash
cd openclaw_foundation && .venv/bin/pytest tests/test_models.py -v
```

Expected: all tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/models/requests.py openclaw_foundation/tests/test_models.py
git commit -m "feat: add optional requested_by field to InvestigationRequest"
```

---

## Task 1: Scaffold `self_service_copilot` Package

**Files:**
- Create: `self_service_copilot/pyproject.toml`
- Create: `self_service_copilot/src/self_service_copilot/__init__.py`
- Create: `self_service_copilot/tests/__init__.py`

- [ ] **Step 1: Create the package directory structure**

```bash
mkdir -p self_service_copilot/src/self_service_copilot
mkdir -p self_service_copilot/tests
touch self_service_copilot/src/self_service_copilot/__init__.py
touch self_service_copilot/tests/__init__.py
```

- [ ] **Step 2: Create `pyproject.toml`**

Create `self_service_copilot/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "self-service-copilot"
version = "0.1.0"
description = "Self-Service Ops Copilot Slack bot"
requires-python = ">=3.11"
dependencies = [
    "openclaw-foundation",
    "slack-bolt>=1.18",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Create venv and install dependencies**

```bash
cd self_service_copilot
python3 -m venv .venv
.venv/bin/pip install -e "../openclaw_foundation"
.venv/bin/pip install -e ".[dev]"
```

- [ ] **Step 4: Verify the package is importable**

```bash
cd self_service_copilot && .venv/bin/python -c "import self_service_copilot; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add self_service_copilot/
git commit -m "feat: scaffold self_service_copilot package"
```

---

## Task 2: `config.py` — `CopilotConfig`

**Files:**
- Create: `self_service_copilot/src/self_service_copilot/config.py`

`CopilotConfig` holds all startup configuration. `from_env()` reads it from environment variables. No unit test for `from_env()` (pure env reading); the dataclass is validated by use in later tasks.

- [ ] **Step 1: Create `config.py`**

```python
from __future__ import annotations

import os
from dataclasses import dataclass

from openclaw_foundation.models.requests import ExecutionBudget


@dataclass
class CopilotConfig:
    cluster: str
    environment: str
    allowed_clusters: set[str]
    allowed_namespaces: set[str]
    supported_tools: frozenset[str]
    default_budget: ExecutionBudget
    provider: str  # "fake" | "real"

    @classmethod
    def from_env(cls) -> CopilotConfig:
        cluster = os.environ["COPILOT_CLUSTER"]
        environment = os.environ["COPILOT_ENVIRONMENT"]
        allowed_clusters = {s.strip() for s in os.environ["COPILOT_ALLOWED_CLUSTERS"].split(",")}
        allowed_namespaces = {s.strip() for s in os.environ["COPILOT_ALLOWED_NAMESPACES"].split(",")}
        provider = os.environ.get("COPILOT_PROVIDER", "fake")
        return cls(
            cluster=cluster,
            environment=environment,
            allowed_clusters=allowed_clusters,
            allowed_namespaces=allowed_namespaces,
            supported_tools=frozenset({"get_pod_status", "get_pod_events"}),
            default_budget=ExecutionBudget(
                max_steps=2,
                max_tool_calls=1,
                max_duration_seconds=15,
                max_output_tokens=512,
            ),
            provider=provider,
        )
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
cd self_service_copilot && .venv/bin/python -c "from self_service_copilot.config import CopilotConfig; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add self_service_copilot/src/self_service_copilot/config.py
git commit -m "feat: add CopilotConfig with from_env constructor"
```

---

## Task 3: `parser.py` + Tests

**Files:**
- Create: `self_service_copilot/src/self_service_copilot/parser.py`
- Create: `self_service_copilot/tests/test_parser.py`

- [ ] **Step 1: Write the failing tests**

Create `self_service_copilot/tests/test_parser.py`:

```python
import pytest

from self_service_copilot.parser import (
    ParsedCommand,
    UnknownCommandError,
    UsageError,
    parse,
)

SUPPORTED = frozenset({"get_pod_status", "get_pod_events"})
BOT_ID = "U123456"


def test_parse_returns_parsed_command_for_valid_input() -> None:
    raw = f"<@{BOT_ID}> get_pod_status payments payments-api-123"
    cmd = parse(raw, BOT_ID, SUPPORTED)

    assert cmd == ParsedCommand(
        tool_name="get_pod_status",
        namespace="payments",
        resource_name="payments-api-123",
        raw_text=raw,
    )


def test_parse_strips_extra_whitespace() -> None:
    cmd = parse(f"<@{BOT_ID}>   get_pod_events   payments   payments-api-123  ", BOT_ID, SUPPORTED)

    assert cmd.tool_name == "get_pod_events"
    assert cmd.namespace == "payments"
    assert cmd.resource_name == "payments-api-123"


def test_parse_raises_unknown_command_error_for_unrecognised_tool() -> None:
    with pytest.raises(UnknownCommandError, match="get_pod_logs"):
        parse(f"<@{BOT_ID}> get_pod_logs payments payments-api-123", BOT_ID, SUPPORTED)


def test_parse_raises_usage_error_for_too_few_arguments() -> None:
    with pytest.raises(UsageError):
        parse(f"<@{BOT_ID}> get_pod_status payments", BOT_ID, SUPPORTED)


def test_parse_raises_usage_error_for_too_many_arguments() -> None:
    with pytest.raises(UsageError):
        parse(f"<@{BOT_ID}> get_pod_status payments pod-123 extra", BOT_ID, SUPPORTED)


def test_parse_raises_usage_error_for_empty_mention() -> None:
    with pytest.raises(UsageError):
        parse(f"<@{BOT_ID}>", BOT_ID, SUPPORTED)


def test_parse_preserves_raw_text() -> None:
    raw = f"<@{BOT_ID}> get_pod_status payments payments-api-123"
    cmd = parse(raw, BOT_ID, SUPPORTED)

    assert cmd.raw_text == raw
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd self_service_copilot && .venv/bin/pytest tests/test_parser.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'self_service_copilot.parser'`

- [ ] **Step 3: Implement `parser.py`**

Create `self_service_copilot/src/self_service_copilot/parser.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedCommand:
    tool_name: str
    namespace: str
    resource_name: str
    raw_text: str


class ParseError(ValueError):
    pass


class UnknownCommandError(ParseError):
    pass


class UsageError(ParseError):
    pass


def parse(text: str, bot_user_id: str, supported_tools: frozenset[str]) -> ParsedCommand:
    raw_text = text
    cleaned = re.sub(rf"<@{re.escape(bot_user_id)}>", "", text).strip()
    tokens = cleaned.split()

    if len(tokens) != 3:
        raise UsageError(
            f"expected: <tool_name> <namespace> <resource_name>, got {len(tokens)} token(s)"
        )

    tool_name, namespace, resource_name = tokens

    if tool_name not in supported_tools:
        raise UnknownCommandError(tool_name)

    return ParsedCommand(
        tool_name=tool_name,
        namespace=namespace,
        resource_name=resource_name,
        raw_text=raw_text,
    )
```

- [ ] **Step 4: Run to verify all tests pass**

```bash
cd self_service_copilot && .venv/bin/pytest tests/test_parser.py -v
```

Expected: 7 tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add self_service_copilot/src/self_service_copilot/parser.py self_service_copilot/tests/test_parser.py
git commit -m "feat: add parser with ParsedCommand and grammar validation"
```

---

## Task 4: `dispatcher.py` + Tests

**Files:**
- Create: `self_service_copilot/src/self_service_copilot/dispatcher.py`
- Create: `self_service_copilot/tests/test_dispatcher.py`

- [ ] **Step 1: Write the failing tests**

Create `self_service_copilot/tests/test_dispatcher.py`:

```python
import pytest

from openclaw_foundation.models.requests import ExecutionBudget

from self_service_copilot.config import CopilotConfig
from self_service_copilot.dispatcher import (
    DispatchError,
    SlackContext,
    build_request,
    make_request_id,
)
from self_service_copilot.parser import ParsedCommand


def make_config(**overrides) -> CopilotConfig:
    defaults = dict(
        cluster="staging-main",
        environment="staging",
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
        supported_tools=frozenset({"get_pod_status", "get_pod_events"}),
        default_budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=15,
            max_output_tokens=512,
        ),
        provider="fake",
    )
    defaults.update(overrides)
    return CopilotConfig(**defaults)


def make_cmd(tool_name: str = "get_pod_status", namespace: str = "payments") -> ParsedCommand:
    return ParsedCommand(
        tool_name=tool_name,
        namespace=namespace,
        resource_name="payments-api-123",
        raw_text=f"@copilot {tool_name} {namespace} payments-api-123",
    )


def make_ctx() -> SlackContext:
    return SlackContext(actor_id="U999", channel_id="C001", event_ts="1234567890.000100")


def test_make_request_id_encodes_channel_and_ts() -> None:
    ctx = SlackContext(actor_id="U999", channel_id="C001", event_ts="1234567890.000100")

    assert make_request_id(ctx) == "slack:C001:1234567890.000100"


def test_build_request_sets_request_id_from_context() -> None:
    request = build_request(make_cmd(), make_ctx(), make_config())

    assert request.request_id == "slack:C001:1234567890.000100"


def test_build_request_sets_input_ref_from_context() -> None:
    request = build_request(make_cmd(), make_ctx(), make_config())

    assert request.input_ref == "slack://C001/1234567890.000100"


def test_build_request_sets_source_product() -> None:
    request = build_request(make_cmd(), make_ctx(), make_config())

    assert request.source_product == "self_service_copilot"


def test_build_request_sets_requested_by_from_actor_id() -> None:
    request = build_request(make_cmd(), make_ctx(), make_config())

    assert request.requested_by == "U999"


def test_build_request_cluster_always_from_config_not_user_input() -> None:
    request = build_request(make_cmd(), make_ctx(), make_config())

    assert request.scope["cluster"] == "staging-main"
    assert request.target["cluster"] == "staging-main"


def test_build_request_target_contains_namespace_and_resource_name() -> None:
    request = build_request(make_cmd(), make_ctx(), make_config())

    assert request.target["namespace"] == "payments"
    assert request.target["resource_name"] == "payments-api-123"


def test_build_request_raises_dispatch_error_for_disallowed_tool() -> None:
    cmd = make_cmd(tool_name="get_pod_logs")

    with pytest.raises(DispatchError, match="get_pod_logs"):
        build_request(cmd, make_ctx(), make_config())


def test_build_request_raises_dispatch_error_for_disallowed_namespace() -> None:
    cmd = make_cmd(namespace="internal")

    with pytest.raises(DispatchError, match="internal"):
        build_request(cmd, make_ctx(), make_config())


def test_build_request_raises_dispatch_error_when_cluster_not_in_allowlist() -> None:
    config = make_config(allowed_clusters={"prod-main"})

    with pytest.raises(DispatchError, match="staging-main"):
        build_request(make_cmd(), make_ctx(), config)
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd self_service_copilot && .venv/bin/pytest tests/test_dispatcher.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'self_service_copilot.dispatcher'`

- [ ] **Step 3: Implement `dispatcher.py`**

Create `self_service_copilot/src/self_service_copilot/dispatcher.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import InvestigationRequest

from self_service_copilot.config import CopilotConfig
from self_service_copilot.parser import ParsedCommand


@dataclass(frozen=True)
class SlackContext:
    actor_id: str
    channel_id: str
    event_ts: str


class DispatchError(ValueError):
    pass


def make_request_id(ctx: SlackContext) -> str:
    return f"slack:{ctx.channel_id}:{ctx.event_ts}"


def build_request(
    cmd: ParsedCommand,
    ctx: SlackContext,
    config: CopilotConfig,
) -> InvestigationRequest:
    if cmd.tool_name not in config.supported_tools:
        raise DispatchError(f"tool {cmd.tool_name!r} is not allowed")
    if cmd.namespace not in config.allowed_namespaces:
        raise DispatchError(f"namespace {cmd.namespace!r} is not allowed")
    if config.cluster not in config.allowed_clusters:
        raise DispatchError(f"cluster {config.cluster!r} is not allowed")

    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id=make_request_id(ctx),
        input_ref=f"slack://{ctx.channel_id}/{ctx.event_ts}",
        source_product="self_service_copilot",
        requested_by=ctx.actor_id,
        scope={
            "cluster": config.cluster,
            "environment": config.environment,
        },
        budget=config.default_budget,
        tool_name=cmd.tool_name,
        target={
            "cluster": config.cluster,
            "namespace": cmd.namespace,
            "resource_name": cmd.resource_name,
        },
    )
```

- [ ] **Step 4: Run to verify all tests pass**

```bash
cd self_service_copilot && .venv/bin/pytest tests/test_dispatcher.py -v
```

Expected: 10 tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add self_service_copilot/src/self_service_copilot/dispatcher.py self_service_copilot/tests/test_dispatcher.py
git commit -m "feat: add dispatcher with SlackContext, DispatchError, and build_request"
```

---

## Task 5: `formatter.py` + Tests

**Files:**
- Create: `self_service_copilot/src/self_service_copilot/formatter.py`
- Create: `self_service_copilot/tests/test_formatter.py`

- [ ] **Step 1: Write the failing tests**

Create `self_service_copilot/tests/test_formatter.py`:

```python
from openclaw_foundation.models.enums import ResultState
from openclaw_foundation.models.responses import CanonicalResponse

from self_service_copilot.dispatcher import DispatchError
from self_service_copilot.formatter import (
    format_dispatch_error,
    format_parse_error,
    format_response,
)
from self_service_copilot.parser import ParsedCommand, UnknownCommandError, UsageError

SUPPORTED = frozenset({"get_pod_status", "get_pod_events"})


def make_cmd(tool_name: str = "get_pod_status") -> ParsedCommand:
    return ParsedCommand(
        tool_name=tool_name,
        namespace="payments",
        resource_name="payments-api-123",
        raw_text=f"<@BOT> {tool_name} payments payments-api-123",
    )


def make_response(result_state: ResultState, summary: str = "pod payments-api-123 is Running") -> CanonicalResponse:
    return CanonicalResponse(
        request_id="slack:C001:1234",
        result_state=result_state,
        summary=summary,
        actions_attempted=["get_pod_status"],
        redaction_applied=True,
    )


def test_format_response_success_starts_with_success_label() -> None:
    reply = format_response(make_response(ResultState.SUCCESS), make_cmd())

    assert reply.startswith("[success]")


def test_format_response_success_includes_tool_and_resource_label() -> None:
    reply = format_response(make_response(ResultState.SUCCESS), make_cmd())

    assert "get_pod_status" in reply
    assert "payments/payments-api-123" in reply


def test_format_response_success_includes_summary() -> None:
    reply = format_response(make_response(ResultState.SUCCESS), make_cmd())

    assert "pod payments-api-123 is Running" in reply


def test_format_response_failed_starts_with_failed_label() -> None:
    reply = format_response(
        make_response(ResultState.FAILED, "no registered tool available for get_pod_status"),
        make_cmd(),
    )

    assert reply.startswith("[failed]")
    assert "no registered tool available" in reply


def test_format_response_fallback_starts_with_fallback_label() -> None:
    reply = format_response(
        make_response(ResultState.FALLBACK, "budget exhausted before tool execution"),
        make_cmd(),
    )

    assert reply.startswith("[fallback]")
    assert "budget exhausted" in reply


def test_format_parse_error_unknown_command_starts_with_unknown_label() -> None:
    error = UnknownCommandError("get_pod_logs")
    reply = format_parse_error(error, SUPPORTED)

    assert reply.startswith("[unknown command]")
    assert "get_pod_logs" in reply


def test_format_parse_error_unknown_command_lists_supported_tools_sorted() -> None:
    error = UnknownCommandError("get_pod_logs")
    reply = format_parse_error(error, SUPPORTED)

    idx_events = reply.index("get_pod_events")
    idx_status = reply.index("get_pod_status")
    assert idx_events < idx_status


def test_format_parse_error_usage_error_starts_with_usage_label() -> None:
    error = UsageError("expected: <tool_name> <namespace> <resource_name>, got 1 token(s)")
    reply = format_parse_error(error, SUPPORTED)

    assert reply.startswith("[usage]")


def test_format_dispatch_error_starts_with_denied_label() -> None:
    error = DispatchError('namespace "internal" is not allowed')
    reply = format_dispatch_error(error, make_cmd())

    assert reply.startswith("[denied]")
    assert "internal" in reply
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd self_service_copilot && .venv/bin/pytest tests/test_formatter.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'self_service_copilot.formatter'`

- [ ] **Step 3: Implement `formatter.py`**

Create `self_service_copilot/src/self_service_copilot/formatter.py`:

```python
from __future__ import annotations

from openclaw_foundation.models.enums import ResultState
from openclaw_foundation.models.responses import CanonicalResponse

from self_service_copilot.dispatcher import DispatchError
from self_service_copilot.parser import ParsedCommand, ParseError, UnknownCommandError


def _resource_label(cmd: ParsedCommand) -> str:
    return f"{cmd.tool_name} {cmd.namespace}/{cmd.resource_name}"


def format_response(response: CanonicalResponse, cmd: ParsedCommand) -> str:
    label = _resource_label(cmd)
    if response.result_state == ResultState.SUCCESS:
        return f"[success] {label}\n{response.summary}"
    if response.result_state == ResultState.FAILED:
        return f"[failed] {label}\n{response.summary}"
    if response.result_state == ResultState.FALLBACK:
        return f"[fallback] {label}\n{response.summary}"
    return f"[{response.result_state}] {label}\n{response.summary}"


def format_parse_error(error: ParseError, supported_tools: frozenset[str]) -> str:
    supported_str = ", ".join(
        f"{t} <namespace> <resource_name>" for t in sorted(supported_tools)
    )
    if isinstance(error, UnknownCommandError):
        return f"[unknown command] {error}\nSupported: {supported_str}"
    return f"[usage] {error}\nSupported: {supported_str}"


def format_dispatch_error(error: DispatchError, cmd: ParsedCommand) -> str:
    return f"[denied] {error}"
```

- [ ] **Step 4: Run to verify all tests pass**

```bash
cd self_service_copilot && .venv/bin/pytest tests/test_formatter.py -v
```

Expected: 9 tests `PASSED`

- [ ] **Step 5: Run full test suite**

```bash
cd self_service_copilot && .venv/bin/pytest tests/ -v
```

Expected: all tests `PASSED`

- [ ] **Step 6: Commit**

```bash
git add self_service_copilot/src/self_service_copilot/formatter.py self_service_copilot/tests/test_formatter.py
git commit -m "feat: add formatter for Slack reply strings"
```

---

## Task 6: `bot.py` — Slack Socket Mode App

**Files:**
- Create: `self_service_copilot/src/self_service_copilot/bot.py`

No unit tests — requires live Slack tokens. Manual smoke test with `COPILOT_PROVIDER=fake`.

- [ ] **Step 1: Create `bot.py`**

Create `self_service_copilot/src/self_service_copilot/bot.py`:

```python
from __future__ import annotations

import logging
import os
import traceback

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from openclaw_foundation.adapters.kubernetes import (
    FakeKubernetesProviderAdapter,
    RealKubernetesProviderAdapter,
    build_core_v1_api,
)
from openclaw_foundation.runtime.runner import OpenClawRunner
from openclaw_foundation.tools.kubernetes_pod_events import KubernetesPodEventsTool
from openclaw_foundation.tools.kubernetes_pod_status import KubernetesPodStatusTool
from openclaw_foundation.tools.registry import ToolRegistry

from self_service_copilot.config import CopilotConfig
from self_service_copilot.dispatcher import DispatchError, SlackContext, build_request
from self_service_copilot.formatter import (
    format_dispatch_error,
    format_parse_error,
    format_response,
)
from self_service_copilot.parser import ParseError, parse

logging.basicConfig(level=logging.INFO)


def build_registry(config: CopilotConfig) -> ToolRegistry:
    if config.provider == "real":
        adapter = RealKubernetesProviderAdapter(build_core_v1_api())
    else:
        adapter = FakeKubernetesProviderAdapter()

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
    return registry


def main() -> None:
    config = CopilotConfig.from_env()
    registry = build_registry(config)
    runner = OpenClawRunner(registry)

    app = App(token=os.environ["SLACK_BOT_TOKEN"])
    bot_user_id: str = app.client.auth_test()["user_id"]

    @app.event("app_mention")
    def handle_mention(event, say) -> None:
        text = event.get("text", "")
        event_ts = event.get("ts", "")
        channel_id = event.get("channel", "")
        actor_id = event.get("user", "")

        ctx = SlackContext(actor_id=actor_id, channel_id=channel_id, event_ts=event_ts)

        try:
            cmd = parse(text, bot_user_id, config.supported_tools)
        except ParseError as error:
            say(format_parse_error(error, config.supported_tools), thread_ts=event_ts)
            return

        try:
            request = build_request(cmd, ctx, config)
        except DispatchError as error:
            say(format_dispatch_error(error, cmd), thread_ts=event_ts)
            return

        try:
            response = runner.run(request)
            say(format_response(response, cmd), thread_ts=event_ts)
        except Exception:
            traceback.print_exc()
            say("[error] unexpected failure, please retry", thread_ts=event_ts)

    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the module imports cleanly**

```bash
cd self_service_copilot && .venv/bin/python -c "from self_service_copilot.bot import main; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Smoke test with fake provider (requires Slack tokens)**

Set env vars and start:

```bash
cd self_service_copilot
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
COPILOT_CLUSTER=staging-main
COPILOT_ENVIRONMENT=staging
COPILOT_ALLOWED_CLUSTERS=staging-main
COPILOT_ALLOWED_NAMESPACES=payments
COPILOT_PROVIDER=fake
.venv/bin/python -m self_service_copilot.bot
```

In Slack, mention the bot: `@copilot get_pod_status payments payments-api-123`

Expected reply in thread:
```
[success] get_pod_status payments/payments-api-123
pod payments-api-123 is Running
```

- [ ] **Step 4: Commit**

```bash
git add self_service_copilot/src/self_service_copilot/bot.py
git commit -m "feat: add Slack Socket Mode bot with mention handler"
```

---

## Spec Coverage Check

| Spec requirement | Covered by |
|---|---|
| `requested_by` optional field in `InvestigationRequest` | Task 0 |
| `self_service_copilot/` independent package | Task 1 |
| `CopilotConfig` with `supported_tools` as single source | Task 2 |
| `ParsedCommand` with `resource_name` (not `pod_name`) | Task 3 |
| `UnknownCommandError` / `UsageError` | Task 3 |
| Token count check before tool_name check | Task 3 `parse()` |
| Whitespace strip + split | Task 3 `parse()` |
| `SlackContext` frozen dataclass | Task 4 |
| `DispatchError` for allowlist violations | Task 4 |
| `make_request_id()` helper | Task 4 |
| `input_ref = slack://{channel_id}/{event_ts}` | Task 4 `build_request()` |
| `cluster` always from config, never user input | Task 4 `build_request()` |
| `requested_by` set from `ctx.actor_id` | Task 4 `build_request()` |
| `format_response()` by `result_state` | Task 5 |
| `format_parse_error()` sorted supported tools | Task 5 |
| `format_dispatch_error()` `[denied]` label | Task 5 |
| `SUCCESS` / `FAILED` / `FALLBACK` handled by formatter | Task 5 |
| `DENIED` handled as `DispatchError` before runner | Task 4 + Task 6 handler |
| `PARTIAL` deferred | Not implemented — correct |
| `bot.py` sync process, no queue | Task 6 |
| Provider wiring from `CopilotConfig`, not hardcoded in `bot.py` | Task 6 `build_registry()` |
| Slack SDK error: log only, no retry | Task 6 catch-all |
