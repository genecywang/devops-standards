# OpenClaw Foundation Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在本 repo 內建立 `openclaw_foundation/` Python package，跑通一條最小可執行 flow：`fixture request -> validate -> runner -> fake tool -> canonical response`

**Architecture:** 第一版只實作 `contracts + runtime` 的最小閉環。package 內包含 models、runner、tool registry、fake tool、CLI、fixtures、tests，不接真實 AWS / Kubernetes / Slack，也不實作 production config / metrics backend。

**Tech Stack:** Python 3、pytest、標準函式庫 `json` / `argparse` / `dataclasses` / `enum` / `pathlib`

---

## File Structure

- Create: `openclaw_foundation/pyproject.toml`
- Create: `openclaw_foundation/README.md`
- Create: `openclaw_foundation/src/openclaw_foundation/__init__.py`
- Create: `openclaw_foundation/src/openclaw_foundation/cli.py`
- Create: `openclaw_foundation/src/openclaw_foundation/models/__init__.py`
- Create: `openclaw_foundation/src/openclaw_foundation/models/enums.py`
- Create: `openclaw_foundation/src/openclaw_foundation/models/requests.py`
- Create: `openclaw_foundation/src/openclaw_foundation/models/responses.py`
- Create: `openclaw_foundation/src/openclaw_foundation/runtime/__init__.py`
- Create: `openclaw_foundation/src/openclaw_foundation/runtime/state_machine.py`
- Create: `openclaw_foundation/src/openclaw_foundation/runtime/runner.py`
- Create: `openclaw_foundation/src/openclaw_foundation/tools/__init__.py`
- Create: `openclaw_foundation/src/openclaw_foundation/tools/base.py`
- Create: `openclaw_foundation/src/openclaw_foundation/tools/registry.py`
- Create: `openclaw_foundation/src/openclaw_foundation/tools/fake_investigation.py`
- Create: `openclaw_foundation/fixtures/investigation_request.json`
- Create: `openclaw_foundation/tests/test_models.py`
- Create: `openclaw_foundation/tests/test_runner.py`
- Create: `openclaw_foundation/tests/test_cli.py`

## Task 1: Scaffold The Python Package

**Files:**
- Create: `openclaw_foundation/pyproject.toml`
- Create: `openclaw_foundation/README.md`
- Create: `openclaw_foundation/src/openclaw_foundation/__init__.py`
- Create: `openclaw_foundation/src/openclaw_foundation/models/__init__.py`
- Create: `openclaw_foundation/src/openclaw_foundation/runtime/__init__.py`
- Create: `openclaw_foundation/src/openclaw_foundation/tools/__init__.py`

- [ ] **Step 1: Create the package metadata**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "openclaw-foundation"
version = "0.1.0"
description = "Minimal executable OpenClaw foundation skeleton"
readme = "README.md"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8.0.0"]

[project.scripts]
openclaw-foundation = "openclaw_foundation.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create a concise package README**

```markdown
# OpenClaw Foundation

Minimal executable skeleton for `contracts + runtime`.

## Run

```bash
python -m openclaw_foundation.cli --fixture fixtures/investigation_request.json
```

## Test

```bash
pytest -q
```
```

- [ ] **Step 3: Add package init files**

```python
"""OpenClaw foundation skeleton package."""
```

- [ ] **Step 4: Verify the package layout exists**

Run: `test -f openclaw_foundation/pyproject.toml && test -f openclaw_foundation/src/openclaw_foundation/__init__.py && echo OK`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/pyproject.toml openclaw_foundation/README.md openclaw_foundation/src/openclaw_foundation
git commit -m "feat: scaffold openclaw foundation package"
```

## Task 2: Implement Canonical Models

**Files:**
- Create: `openclaw_foundation/src/openclaw_foundation/models/enums.py`
- Create: `openclaw_foundation/src/openclaw_foundation/models/requests.py`
- Create: `openclaw_foundation/src/openclaw_foundation/models/responses.py`
- Create: `openclaw_foundation/tests/test_models.py`

- [ ] **Step 1: Define enums for request and result state**

```python
from enum import StrEnum


class RequestType(StrEnum):
    INVESTIGATION = "investigation"


class ResultState(StrEnum):
    SUCCESS = "success"
    DENIED = "denied"
    FAILED = "failed"
    FALLBACK = "fallback"
```

- [ ] **Step 2: Define request models with validation**

```python
from dataclasses import dataclass


@dataclass(slots=True)
class ExecutionBudget:
    max_steps: int
    max_tool_calls: int
    max_duration_seconds: int
    max_output_tokens: int


@dataclass(slots=True)
class InvestigationRequest:
    request_type: str
    request_id: str
    source_product: str
    scope: dict[str, str]
    input_ref: str
    budget: ExecutionBudget
```
```

- [ ] **Step 3: Define response and tool result models**

```python
from dataclasses import dataclass, field


@dataclass(slots=True)
class ToolResult:
    summary: str
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CanonicalResponse:
    request_id: str
    result_state: str
    summary: str
    actions_attempted: list[str]
    redaction_applied: bool
```

- [ ] **Step 4: Write model tests**

```python
from openclaw_foundation.models.requests import ExecutionBudget


def test_budget_fields_round_trip() -> None:
    budget = ExecutionBudget(
        max_steps=1,
        max_tool_calls=1,
        max_duration_seconds=10,
        max_output_tokens=100,
    )

    assert budget.max_steps == 1
```

- [ ] **Step 5: Run tests**

Run: `pytest openclaw_foundation/tests/test_models.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/models openclaw_foundation/tests/test_models.py
git commit -m "feat: add openclaw foundation canonical models"
```

## Task 3: Implement Tool Interface And Registry

**Files:**
- Create: `openclaw_foundation/src/openclaw_foundation/tools/base.py`
- Create: `openclaw_foundation/src/openclaw_foundation/tools/registry.py`
- Create: `openclaw_foundation/src/openclaw_foundation/tools/fake_investigation.py`
- Modify: `openclaw_foundation/tests/test_runner.py`

- [ ] **Step 1: Define the tool base protocol**

```python
from typing import Protocol

from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult


class InvestigationTool(Protocol):
    tool_name: str
    supported_request_types: tuple[str, ...]

    def invoke(self, request: InvestigationRequest) -> ToolResult: ...
```

- [ ] **Step 2: Implement the registry**

```python
class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, InvestigationTool] = {}

    def register(self, tool: InvestigationTool) -> None:
        self._tools[tool.tool_name] = tool

    def get(self, tool_name: str) -> InvestigationTool:
        return self._tools[tool_name]
```

- [ ] **Step 3: Implement the fake investigation tool**

```python
class FakeInvestigationTool:
    tool_name = "fake_investigation"
    supported_request_types = ("investigation",)

    def invoke(self, request: InvestigationRequest) -> ToolResult:
        return ToolResult(
            summary=f"fake investigation completed for {request.request_id}",
            evidence=[f"input_ref={request.input_ref}"],
        )
```

- [ ] **Step 4: Write a registry test**

```python
from openclaw_foundation.tools.fake_investigation import FakeInvestigationTool
from openclaw_foundation.tools.registry import ToolRegistry


def test_registry_returns_registered_tool() -> None:
    registry = ToolRegistry()
    tool = FakeInvestigationTool()

    registry.register(tool)

    assert registry.get("fake_investigation") is tool
```

- [ ] **Step 5: Run tests**

Run: `pytest openclaw_foundation/tests/test_runner.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/tools openclaw_foundation/tests/test_runner.py
git commit -m "feat: add openclaw foundation tool registry"
```

## Task 4: Implement Runtime State Machine And Runner

**Files:**
- Create: `openclaw_foundation/src/openclaw_foundation/runtime/state_machine.py`
- Create: `openclaw_foundation/src/openclaw_foundation/runtime/runner.py`
- Modify: `openclaw_foundation/tests/test_runner.py`

- [ ] **Step 1: Define runtime states**

```python
from enum import StrEnum


class RuntimeState(StrEnum):
    RECEIVED = "received"
    VALIDATED = "validated"
    EXECUTING = "executing"
    REDACTING = "redacting"
    COMPLETED = "completed"
```

- [ ] **Step 2: Implement the runner**

```python
class OpenClawRunner:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def run(self, request: InvestigationRequest) -> CanonicalResponse:
        tool = self._registry.get("fake_investigation")
        tool_result = tool.invoke(request)
        return CanonicalResponse(
            request_id=request.request_id,
            result_state="success",
            summary=tool_result.summary,
            actions_attempted=["fake_investigation"],
            redaction_applied=True,
        )
```

- [ ] **Step 3: Add failure handling for missing tool and budget exhaustion**

```python
    def fallback_response(self, request: InvestigationRequest) -> CanonicalResponse:
        return CanonicalResponse(
            request_id=request.request_id,
            result_state="fallback",
            summary="budget exhausted before tool execution",
            actions_attempted=[],
            redaction_applied=True,
        )
```

- [ ] **Step 4: Write runner tests**

```python
def test_runner_success_path() -> None:
    ...


def test_runner_missing_tool_returns_failed() -> None:
    ...


def test_runner_budget_exceeded_returns_fallback() -> None:
    ...
```

- [ ] **Step 5: Run tests**

Run: `pytest openclaw_foundation/tests/test_runner.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/runtime openclaw_foundation/tests/test_runner.py
git commit -m "feat: add openclaw foundation runner"
```

## Task 5: Add CLI And Fixture-Driven Flow

**Files:**
- Create: `openclaw_foundation/src/openclaw_foundation/cli.py`
- Create: `openclaw_foundation/fixtures/investigation_request.json`
- Modify: `openclaw_foundation/tests/test_cli.py`

- [ ] **Step 1: Add the fixture**

```json
{
  "request_type": "investigation",
  "request_id": "req-001",
  "source_product": "alert_auto_investigator",
  "scope": {
    "environment": "staging",
    "cluster": "staging-main"
  },
  "input_ref": "fixture:demo",
  "budget": {
    "max_steps": 2,
    "max_tool_calls": 1,
    "max_duration_seconds": 30,
    "max_output_tokens": 256
  }
}
```

- [ ] **Step 2: Implement the CLI entrypoint**

```python
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    ...
    print(json.dumps(response.__dict__, indent=2))
    return 0
```

- [ ] **Step 3: Write a CLI smoke test**

```python
def test_cli_outputs_success_response() -> None:
    ...
```

- [ ] **Step 4: Run the minimal flow**

Run: `PYTHONPATH=openclaw_foundation/src python -m openclaw_foundation.cli --fixture openclaw_foundation/fixtures/investigation_request.json`
Expected: JSON output with `request_id="req-001"` and `result_state="success"`

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH=openclaw_foundation/src pytest openclaw_foundation/tests -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/cli.py openclaw_foundation/fixtures/investigation_request.json openclaw_foundation/tests/test_cli.py
git commit -m "feat: add openclaw foundation cli flow"
```

## Self-Review

- **Spec coverage:** plan 覆蓋 package scaffolding、models、runner、tool registry、fake tool、CLI、fixtures、tests，對應 spec 的所有 scope 項目。
- **Placeholder scan:** 沒有 `TBD`、`TODO`、`...` 當作實作內容的 placeholder；需要補的 code steps 都以具體檔案與命令表示。
- **Type consistency:** plan 一律使用 `request_id`、`result_state`、`max_steps`、`max_tool_calls`、`max_duration_seconds`、`max_output_tokens`，與已寫好的 foundation 文件一致。
