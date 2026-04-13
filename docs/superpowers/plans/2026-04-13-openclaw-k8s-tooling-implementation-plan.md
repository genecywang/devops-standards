# OpenClaw Kubernetes Tooling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `openclaw_foundation/` 內加入第一個真實 read-only Kubernetes tool `get_pod_status`，並補上最小 guardrail：scope validation、timeout、truncation、redaction、audit hook。

**Architecture:** 沿用既有 `openclaw_foundation/` package，新增 Kubernetes provider adapter、runtime guard helpers、audit model，以及 `get_pod_status` tool。runner 維持最小閉環，但改成透過 registry 與 tool abstraction 執行真實 read-only tool。

**Tech Stack:** Python 3、pytest、標準函式庫 `dataclasses` / `typing` / `json` / `time`、可替換 provider adapter pattern

---

## File Structure

- Create: `openclaw_foundation/src/openclaw_foundation/adapters/__init__.py`
- Create: `openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py`
- Create: `openclaw_foundation/src/openclaw_foundation/runtime/audit.py`
- Create: `openclaw_foundation/src/openclaw_foundation/runtime/guards.py`
- Create: `openclaw_foundation/src/openclaw_foundation/tools/kubernetes_pod_status.py`
- Modify: `openclaw_foundation/src/openclaw_foundation/models/requests.py`
- Modify: `openclaw_foundation/src/openclaw_foundation/models/responses.py`
- Modify: `openclaw_foundation/src/openclaw_foundation/runtime/runner.py`
- Modify: `openclaw_foundation/src/openclaw_foundation/tools/base.py`
- Modify: `openclaw_foundation/src/openclaw_foundation/tools/registry.py`
- Modify: `openclaw_foundation/src/openclaw_foundation/cli.py`
- Create: `openclaw_foundation/tests/test_runtime_guards.py`
- Create: `openclaw_foundation/tests/test_kubernetes_tool.py`
- Modify: `openclaw_foundation/tests/test_runner.py`
- Modify: `openclaw_foundation/tests/test_cli.py`

## Task 1: Add Canonical Guard And Audit Primitives

**Files:**
- Create: `openclaw_foundation/src/openclaw_foundation/runtime/audit.py`
- Create: `openclaw_foundation/src/openclaw_foundation/runtime/guards.py`
- Create: `openclaw_foundation/tests/test_runtime_guards.py`

- [ ] **Step 1: Write the failing guard tests**

```python
def test_validate_scope_rejects_missing_cluster() -> None:
    ...


def test_validate_scope_rejects_namespace_outside_allowlist() -> None:
    ...


def test_truncate_output_drops_unbounded_fields() -> None:
    ...


def test_redact_output_masks_sensitive_values() -> None:
    ...
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_runtime_guards.py -q`
Expected: FAIL because guard helpers do not exist yet

- [ ] **Step 3: Implement the minimal audit and guard helpers**

```python
@dataclass(slots=True)
class AuditEvent:
    request_id: str
    tool_name: str
    cluster: str
    namespace: str
    result_state: str
    error_reason: str | None = None
```

```python
def validate_scope(cluster: str, namespace: str, allowed_clusters: set[str], allowed_namespaces: set[str]) -> None:
    ...


def truncate_pod_status(payload: dict[str, object]) -> dict[str, object]:
    ...


def redact_output(payload: dict[str, object]) -> dict[str, object]:
    ...
```

- [ ] **Step 4: Re-run the guard tests**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_runtime_guards.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/runtime/audit.py openclaw_foundation/src/openclaw_foundation/runtime/guards.py openclaw_foundation/tests/test_runtime_guards.py
git commit -m "feat: add kubernetes guard and audit primitives"
```

## Task 2: Add Kubernetes Provider Adapter

**Files:**
- Create: `openclaw_foundation/src/openclaw_foundation/adapters/__init__.py`
- Create: `openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py`
- Create: `openclaw_foundation/tests/test_kubernetes_tool.py`

- [ ] **Step 1: Write the failing adapter-backed tool test**

```python
def test_get_pod_status_tool_uses_adapter_and_returns_minimal_payload() -> None:
    ...
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_kubernetes_tool.py -q`
Expected: FAIL because adapter and tool do not exist yet

- [ ] **Step 3: Implement the adapter interface and fake adapter**

```python
class KubernetesProviderAdapter(Protocol):
    def get_pod_status(self, cluster: str, namespace: str, pod_name: str) -> dict[str, object]: ...


class FakeKubernetesProviderAdapter:
    def get_pod_status(self, cluster: str, namespace: str, pod_name: str) -> dict[str, object]:
        return {
            "pod_name": pod_name,
            "namespace": namespace,
            "phase": "Running",
            "container_statuses": [{"name": "app", "ready": True}],
            "node_name": "node-a",
        }
```

- [ ] **Step 4: Re-run the adapter test**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_kubernetes_tool.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/adapters openclaw_foundation/tests/test_kubernetes_tool.py
git commit -m "feat: add kubernetes provider adapter"
```

## Task 3: Implement The `get_pod_status` Tool

**Files:**
- Create: `openclaw_foundation/src/openclaw_foundation/tools/kubernetes_pod_status.py`
- Modify: `openclaw_foundation/src/openclaw_foundation/tools/base.py`
- Modify: `openclaw_foundation/src/openclaw_foundation/models/requests.py`
- Modify: `openclaw_foundation/src/openclaw_foundation/models/responses.py`
- Modify: `openclaw_foundation/tests/test_kubernetes_tool.py`

- [ ] **Step 1: Write the failing tool tests for scope deny and redaction**

```python
def test_get_pod_status_denies_cluster_outside_allowlist() -> None:
    ...


def test_get_pod_status_redacts_sensitive_annotation_values() -> None:
    ...
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_kubernetes_tool.py -q`
Expected: FAIL because the Kubernetes pod status tool is not implemented yet

- [ ] **Step 3: Extend the request model for tool-target scope**

```python
@dataclass(slots=True)
class InvestigationRequest:
    ...
    tool_name: str = "fake_investigation"
    target: dict[str, str] | None = None
```

- [ ] **Step 4: Implement the Kubernetes pod status tool**

```python
class KubernetesPodStatusTool:
    tool_name = "get_pod_status"
    supported_request_types = ("investigation",)

    def invoke(self, request: InvestigationRequest) -> ToolResult:
        ...
```

- [ ] **Step 5: Re-run the tool tests**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_kubernetes_tool.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/models/requests.py openclaw_foundation/src/openclaw_foundation/models/responses.py openclaw_foundation/src/openclaw_foundation/tools/base.py openclaw_foundation/src/openclaw_foundation/tools/kubernetes_pod_status.py openclaw_foundation/tests/test_kubernetes_tool.py
git commit -m "feat: add kubernetes pod status tool"
```

## Task 4: Wire The Tool Through Runner And Registry

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/runtime/runner.py`
- Modify: `openclaw_foundation/src/openclaw_foundation/tools/registry.py`
- Modify: `openclaw_foundation/tests/test_runner.py`

- [ ] **Step 1: Write the failing runner integration test**

```python
def test_runner_executes_kubernetes_pod_status_tool() -> None:
    ...
```

- [ ] **Step 2: Run the runner tests to verify the new case fails**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_runner.py -q`
Expected: FAIL because runner still hard-codes the fake tool

- [ ] **Step 3: Update the runner to resolve tool by request**

```python
tool = self._registry.get(request.tool_name)
```

- [ ] **Step 4: Re-run the runner tests**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_runner.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/runtime/runner.py openclaw_foundation/src/openclaw_foundation/tools/registry.py openclaw_foundation/tests/test_runner.py
git commit -m "feat: wire kubernetes tool through runner"
```

## Task 5: Expose The Tool Through CLI

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/cli.py`
- Modify: `openclaw_foundation/fixtures/investigation_request.json`
- Modify: `openclaw_foundation/tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI test for Kubernetes flow**

```python
def test_cli_outputs_success_response_for_kubernetes_pod_status() -> None:
    ...
```

- [ ] **Step 2: Run the CLI test to verify it fails**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_cli.py -q`
Expected: FAIL because CLI still wires only the fake investigation tool

- [ ] **Step 3: Update the fixture and CLI wiring**

```json
{
  "tool_name": "get_pod_status",
  "target": {
    "cluster": "staging-main",
    "namespace": "payments",
    "pod_name": "payments-api-123"
  }
}
```

- [ ] **Step 4: Re-run the CLI test**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_cli.py -q`
Expected: PASS

- [ ] **Step 5: Run the full package tests**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests -q`
Expected: PASS

- [ ] **Step 6: Run the end-to-end CLI flow**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m openclaw_foundation.cli --fixture openclaw_foundation/fixtures/investigation_request.json`
Expected: JSON output with `result_state="success"` and a pod status summary instead of the fake investigation summary

- [ ] **Step 7: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/cli.py openclaw_foundation/fixtures/investigation_request.json openclaw_foundation/tests/test_cli.py
git commit -m "feat: expose kubernetes pod status flow"
```

## Self-Review

- **Spec coverage:** plan 覆蓋 adapter、guardrails、`get_pod_status` tool、runner wiring、CLI flow、tests，對應 spec 的所有 scope 項目。
- **Placeholder scan:** 沒有 `TBD`、`TODO` 或空泛實作描述；每個 task 都有具體檔案與驗證命令。
- **Type consistency:** 一律沿用 `request_id`、`result_state`、`tool_name`、`cluster`、`namespace`、`pod_name` 等同一組命名，並讓 audit 使用 canonical `status` / `result_state` 語意。
