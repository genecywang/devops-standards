# get_deployment_status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在既有 adapter / guardrail / error model 邊界上，新增第三個 read-only Kubernetes tool：`get_deployment_status`。

**Architecture:** 沿用 Adapter-first 架構，先在 `KubernetesProviderAdapter` Protocol、`FakeKubernetesProviderAdapter`、`RealKubernetesProviderAdapter` 各自加入 `get_deployment_status`，再建立 `KubernetesDeploymentStatusTool`，最後在 CLI 註冊。Guardrail 層沿用既有 `redact_output`，新增最小 deployment status truncation，限制 conditions 數量與 message 長度。

**Tech Stack:** Python 3.12, kubernetes-client, pytest, 既有 `openclaw_foundation` 內部 models / guards / runtime。

---

## File Map

| 操作 | 路徑 | 變更說明 |
|------|------|----------|
| Modify | `openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py` | Protocol + Fake + Real 各加 `get_deployment_status` |
| Modify | `openclaw_foundation/src/openclaw_foundation/runtime/guards.py` | 加 `truncate_deployment_status` |
| Create | `openclaw_foundation/src/openclaw_foundation/tools/kubernetes_deployment_status.py` | `KubernetesDeploymentStatusTool` |
| Modify | `openclaw_foundation/src/openclaw_foundation/cli.py` | 引入並註冊 `KubernetesDeploymentStatusTool` |
| Create | `openclaw_foundation/fixtures/deployment_status_request.json` | CLI 子程序測試用 fixture |
| Modify | `openclaw_foundation/tests/test_kubernetes_adapter.py` | Fake + Real `get_deployment_status` 測試 |
| Modify | `openclaw_foundation/tests/test_runtime_guards.py` | `truncate_deployment_status` 測試 |
| Create | `openclaw_foundation/tests/test_kubernetes_deployment_status_tool.py` | `KubernetesDeploymentStatusTool` 測試 |
| Modify | `openclaw_foundation/tests/test_cli.py` | deployment fixture 的 CLI 子程序測試 |

---

## Task 1: Extend Protocol + Fake Adapter with `get_deployment_status`

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py`
- Modify: `openclaw_foundation/tests/test_kubernetes_adapter.py`

- [ ] **Step 1: Write the failing tests**

在 `test_kubernetes_adapter.py` 加：

```python
from openclaw_foundation.adapters.kubernetes import FakeKubernetesProviderAdapter


def test_fake_adapter_get_deployment_status_returns_bounded_payload() -> None:
    adapter = FakeKubernetesProviderAdapter()

    result = adapter.get_deployment_status(
        cluster="staging-main",
        namespace="payments",
        deployment_name="payments-api",
    )

    assert result["deployment_name"] == "payments-api"
    assert result["desired_replicas"] == 3
    assert isinstance(result["conditions"], list)
    assert set(result["conditions"][0].keys()) == {"type", "status", "reason", "message"}


def test_fake_adapter_get_deployment_status_contains_redactable_condition_message() -> None:
    adapter = FakeKubernetesProviderAdapter()

    result = adapter.get_deployment_status(
        cluster="staging-main",
        namespace="payments",
        deployment_name="payments-api",
    )

    all_messages = " ".join(str(c["message"]) for c in result["conditions"])
    assert "Bearer" in all_messages
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd openclaw_foundation && .venv/bin/pytest tests/test_kubernetes_adapter.py::test_fake_adapter_get_deployment_status_returns_bounded_payload tests/test_kubernetes_adapter.py::test_fake_adapter_get_deployment_status_contains_redactable_condition_message -v
```

Expected: `FAILED` — `AttributeError: 'FakeKubernetesProviderAdapter' object has no attribute 'get_deployment_status'`

- [ ] **Step 3: Implement**

在 `adapters/kubernetes.py` 中：

```python
class KubernetesProviderAdapter(Protocol):
    def get_pod_status(self, cluster: str, namespace: str, pod_name: str) -> dict[str, object]: ...
    def get_pod_events(self, cluster: str, namespace: str, pod_name: str) -> list[dict[str, object]]: ...
    def get_deployment_status(self, cluster: str, namespace: str, deployment_name: str) -> dict[str, object]: ...
```

在 `FakeKubernetesProviderAdapter` 中新增方法：

```python
    def get_deployment_status(
        self,
        cluster: str,
        namespace: str,
        deployment_name: str,
    ) -> dict[str, object]:
        return {
            "deployment_name": deployment_name,
            "namespace": namespace,
            "desired_replicas": 3,
            "ready_replicas": 3,
            "available_replicas": 3,
            "updated_replicas": 3,
            "conditions": [
                {
                    "type": "Available",
                    "status": "True",
                    "reason": "MinimumReplicasAvailable",
                    "message": "Deployment is available. Bearer secret-rollout-token",
                }
            ],
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd openclaw_foundation && .venv/bin/pytest tests/test_kubernetes_adapter.py::test_fake_adapter_get_deployment_status_returns_bounded_payload tests/test_kubernetes_adapter.py::test_fake_adapter_get_deployment_status_contains_redactable_condition_message -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py openclaw_foundation/tests/test_kubernetes_adapter.py
git commit -m "feat: extend kubernetes adapter protocol and fake provider with get_deployment_status"
```

---

## Task 2: Add `truncate_deployment_status` Guard

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/runtime/guards.py`
- Modify: `openclaw_foundation/tests/test_runtime_guards.py`

- [ ] **Step 1: Write the failing tests**

在 `test_runtime_guards.py` 新增：

```python
from openclaw_foundation.runtime.guards import truncate_deployment_status


def test_truncate_deployment_status_limits_conditions_to_five() -> None:
    payload = {
        "conditions": [
            {"type": f"T{i}", "status": "True", "reason": "R", "message": "m"}
            for i in range(8)
        ]
    }

    result = truncate_deployment_status(payload)

    assert len(result["conditions"]) == 5


def test_truncate_deployment_status_truncates_long_condition_message() -> None:
    payload = {
        "conditions": [
            {
                "type": "Available",
                "status": "False",
                "reason": "R",
                "message": "x" * 300,
            }
        ]
    }

    result = truncate_deployment_status(payload)

    assert result["conditions"][0]["message"].endswith("...[truncated]")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd openclaw_foundation && .venv/bin/pytest tests/test_runtime_guards.py::test_truncate_deployment_status_limits_conditions_to_five tests/test_runtime_guards.py::test_truncate_deployment_status_truncates_long_condition_message -v
```

Expected: `ImportError` 或 `AttributeError`

- [ ] **Step 3: Implement**

在 `guards.py` 中新增：

```python
_MAX_DEPLOYMENT_CONDITIONS = 5
_MAX_CONDITION_MESSAGE_LEN = 256


def truncate_deployment_status(payload: dict[str, object]) -> dict[str, object]:
    result = dict(payload)
    conditions = list(result.get("conditions", []))[:_MAX_DEPLOYMENT_CONDITIONS]
    bounded_conditions = []
    for condition in conditions:
        entry = dict(condition)
        message = entry.get("message")
        if isinstance(message, str) and len(message) > _MAX_CONDITION_MESSAGE_LEN:
            entry["message"] = message[:_MAX_CONDITION_MESSAGE_LEN] + "...[truncated]"
        bounded_conditions.append(entry)
    result["conditions"] = bounded_conditions
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd openclaw_foundation && .venv/bin/pytest tests/test_runtime_guards.py::test_truncate_deployment_status_limits_conditions_to_five tests/test_runtime_guards.py::test_truncate_deployment_status_truncates_long_condition_message -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/runtime/guards.py openclaw_foundation/tests/test_runtime_guards.py
git commit -m "feat: add deployment status truncation guard"
```

---

## Task 3: Implement `KubernetesDeploymentStatusTool`

**Files:**
- Create: `openclaw_foundation/src/openclaw_foundation/tools/kubernetes_deployment_status.py`
- Create: `openclaw_foundation/tests/test_kubernetes_deployment_status_tool.py`

- [ ] **Step 1: Write the failing tests**

Create `test_kubernetes_deployment_status_tool.py`:

```python
import pytest

from openclaw_foundation.adapters.kubernetes import FakeKubernetesProviderAdapter
from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.tools.kubernetes_deployment_status import KubernetesDeploymentStatusTool


def make_request(namespace: str = "payments") -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-deploy-001",
        source_product="self_service_copilot",
        scope={"environment": "staging", "cluster": "staging-main"},
        input_ref="fixture:deployment-status",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=30,
            max_output_tokens=256,
        ),
        tool_name="get_deployment_status",
        target={
            "cluster": "staging-main",
            "namespace": namespace,
            "resource_name": "payments-api",
        },
    )


def test_get_deployment_status_tool_uses_adapter_and_returns_summary() -> None:
    tool = KubernetesDeploymentStatusTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
    )

    result = tool.invoke(make_request())

    assert "payments-api" in result.summary
    assert len(result.evidence) == 1
    assert result.evidence[0]["desired_replicas"] == 3


def test_get_deployment_status_tool_denies_cluster_outside_allowlist() -> None:
    tool = KubernetesDeploymentStatusTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"prod-main"},
        allowed_namespaces={"payments"},
    )

    with pytest.raises(PermissionError, match="cluster is not allowed"):
        tool.invoke(make_request())


def test_get_deployment_status_tool_redacts_condition_messages() -> None:
    tool = KubernetesDeploymentStatusTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
    )

    result = tool.invoke(make_request())

    all_messages = " ".join(str(c["message"]) for c in result.evidence[0]["conditions"])
    assert "secret-rollout-token" not in all_messages
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd openclaw_foundation && .venv/bin/pytest tests/test_kubernetes_deployment_status_tool.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement**

Create `kubernetes_deployment_status.py`:

```python
from openclaw_foundation.adapters.kubernetes import KubernetesProviderAdapter
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult
from openclaw_foundation.runtime.guards import (
    redact_output,
    truncate_deployment_status,
    validate_scope,
)


class KubernetesDeploymentStatusTool:
    tool_name = "get_deployment_status"
    supported_request_types = ("investigation",)

    def __init__(
        self,
        adapter: KubernetesProviderAdapter,
        allowed_clusters: set[str],
        allowed_namespaces: set[str],
    ) -> None:
        self._adapter = adapter
        self._allowed_clusters = allowed_clusters
        self._allowed_namespaces = allowed_namespaces

    def invoke(self, request: InvestigationRequest) -> ToolResult:
        if request.target is None:
            raise ValueError("target is required for get_deployment_status")

        cluster = request.target["cluster"]
        namespace = request.target["namespace"]
        deployment_name = request.target.get("resource_name") or request.target.get("deployment_name")
        if deployment_name is None:
            raise ValueError("resource_name or deployment_name is required for get_deployment_status")

        validate_scope(cluster, namespace, self._allowed_clusters, self._allowed_namespaces)

        payload = self._adapter.get_deployment_status(cluster, namespace, deployment_name)
        truncated = truncate_deployment_status(payload)
        redacted = redact_output(truncated)

        desired = redacted.get("desired_replicas", 0)
        ready = redacted.get("ready_replicas", 0)
        available = redacted.get("available_replicas", 0)
        health = "healthy" if desired == ready == available else "degraded"

        return ToolResult(
            summary=f"deployment {deployment_name} is {health}: {ready}/{desired} ready, {available} available",
            evidence=[redacted],
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd openclaw_foundation && .venv/bin/pytest tests/test_kubernetes_deployment_status_tool.py -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/tools/kubernetes_deployment_status.py openclaw_foundation/tests/test_kubernetes_deployment_status_tool.py
git commit -m "feat: add kubernetes deployment status tool"
```

---

## Task 4: Extend Real Adapter with `get_deployment_status`

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py`
- Modify: `openclaw_foundation/tests/test_kubernetes_adapter.py`

- [ ] **Step 1: Write the failing tests**

在 `test_kubernetes_adapter.py` 補：

```python
from types import SimpleNamespace

from openclaw_foundation.adapters.kubernetes import RealKubernetesProviderAdapter


def test_real_adapter_get_deployment_status_maps_minimal_fields() -> None:
    deployment = SimpleNamespace(
        metadata=SimpleNamespace(name="payments-api"),
        status=SimpleNamespace(
            ready_replicas=2,
            available_replicas=2,
            updated_replicas=3,
            conditions=[
                SimpleNamespace(
                    type="Available",
                    status="True",
                    reason="MinimumReplicasAvailable",
                    message="Deployment has minimum availability.",
                )
            ],
        ),
        spec=SimpleNamespace(replicas=3),
    )
    fake_api = SimpleNamespace(read_namespaced_deployment_status=lambda name, namespace: deployment)
    adapter = RealKubernetesProviderAdapter(core_v1_api=None)
    adapter._apps_v1_api = fake_api

    result = adapter.get_deployment_status("staging-main", "payments", "payments-api")

    assert result["deployment_name"] == "payments-api"
    assert result["desired_replicas"] == 3
    assert result["ready_replicas"] == 2
    assert result["conditions"][0]["type"] == "Available"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd openclaw_foundation && .venv/bin/pytest tests/test_kubernetes_adapter.py::test_real_adapter_get_deployment_status_maps_minimal_fields -v
```

Expected: `AttributeError`

- [ ] **Step 3: Implement**

在 `kubernetes.py`：

- `build_core_v1_api()` 旁邊新增 `build_apps_v1_api()`
- `RealKubernetesProviderAdapter` 改成同時持有 `core_v1_api` 與 `apps_v1_api`
- 補 `get_deployment_status()`

Real adapter mapping 方向：

```python
return {
    "deployment_name": deployment.metadata.name,
    "namespace": namespace,
    "desired_replicas": getattr(deployment.spec, "replicas", 0) or 0,
    "ready_replicas": getattr(deployment.status, "ready_replicas", 0) or 0,
    "available_replicas": getattr(deployment.status, "available_replicas", 0) or 0,
    "updated_replicas": getattr(deployment.status, "updated_replicas", 0) or 0,
    "conditions": [...],
}
```

Error mapping 沿用既有 Kubernetes domain errors：

- `401/403` → `KubernetesAccessDeniedError`
- `404` → `KubernetesResourceNotFoundError`
- endpoint / DNS 問題 → `KubernetesEndpointUnreachableError`
- 其他 → `KubernetesApiError`

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd openclaw_foundation && .venv/bin/pytest tests/test_kubernetes_adapter.py::test_real_adapter_get_deployment_status_maps_minimal_fields -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py openclaw_foundation/tests/test_kubernetes_adapter.py
git commit -m "feat: add real kubernetes deployment status adapter"
```

---

## Task 5: CLI Wiring + Fixture

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/cli.py`
- Create: `openclaw_foundation/fixtures/deployment_status_request.json`
- Modify: `openclaw_foundation/tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

在 `test_cli.py` 補一個 deployment status fixture 驗證：

```python
def test_main_with_deployment_status_fixture_prints_success_response(capsys) -> None:
    exit_code = main(
        [
            "--fixture",
            "openclaw_foundation/fixtures/deployment_status_request.json",
            "--provider",
            "fake",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "SUCCESS" in captured.out
    assert "get_deployment_status" in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_cli.py::test_main_with_deployment_status_fixture_prints_success_response -q
```

Expected: `FAILED`

- [ ] **Step 3: Implement**

- 建 `deployment_status_request.json`
- `cli.py` 引入並註冊 `KubernetesDeploymentStatusTool`
- `real` provider 時建立 `apps_v1_api`

fixture 方向：

```json
{
  "request_type": "investigation",
  "request_id": "req-deploy-cli-001",
  "source_product": "cli",
  "scope": {
    "environment": "staging",
    "cluster": "staging-main"
  },
  "input_ref": "fixture:deployment-status",
  "budget": {
    "max_steps": 2,
    "max_tool_calls": 1,
    "max_duration_seconds": 15,
    "max_output_tokens": 512
  },
  "tool_name": "get_deployment_status",
  "target": {
    "cluster": "staging-main",
    "namespace": "payments",
    "resource_name": "payments-api"
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_cli.py::test_main_with_deployment_status_fixture_prints_success_response -q
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/cli.py openclaw_foundation/fixtures/deployment_status_request.json openclaw_foundation/tests/test_cli.py
git commit -m "feat: wire deployment status tool into cli"
```

---

## Verification Checklist

- [ ] `FakeKubernetesProviderAdapter.get_deployment_status()` 回固定 bounded payload
- [ ] `truncate_deployment_status()` 會限制 conditions 數量與 message 長度
- [ ] `KubernetesDeploymentStatusTool` 可處理 `resource_name`
- [ ] real adapter 正確 map deployment status 欄位與錯誤語意
- [ ] CLI fixture 可跑通 `get_deployment_status`
- [ ] 不引入 pod correlation / logs / Prometheus
