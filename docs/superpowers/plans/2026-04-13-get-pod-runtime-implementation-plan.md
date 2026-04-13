# get_pod_runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在既有 `openclaw_foundation` 上新增第一個 Prometheus-backed preset：`get_pod_runtime`。

**Architecture:** 新增 Prometheus adapter 邊界，提供 `get_pod_runtime(namespace, pod_name)`。第一版固定查 `kube_pod_status_ready`、`kube_pod_container_status_restarts_total`、`sum(increase(...[15m]))`，並由 `Kubernetes` / `Slack` 現有 grammar 直接用 `resource_name` 傳 pod name。Slack formatter 仍只吃 summary。

**Tech Stack:** Python 3.12, `requests` 或標準 `urllib`, Prometheus HTTP API, pytest, 既有 `openclaw_foundation` models / runtime / CLI / `self_service_copilot`。

---

## File Map

| 操作 | 路徑 | 變更說明 |
|------|------|----------|
| Create | `openclaw_foundation/src/openclaw_foundation/adapters/prometheus.py` | Prometheus adapter + fake / real provider |
| Create | `openclaw_foundation/src/openclaw_foundation/tools/prometheus_pod_runtime.py` | `PrometheusPodRuntimeTool` |
| Create | `openclaw_foundation/tests/test_prometheus_adapter.py` | fake / real adapter tests |
| Create | `openclaw_foundation/tests/test_prometheus_pod_runtime_tool.py` | tool tests |
| Modify | `openclaw_foundation/src/openclaw_foundation/cli.py` | 註冊 `get_pod_runtime` |
| Create | `openclaw_foundation/fixtures/pod_runtime_request.json` | CLI fixture |
| Modify | `openclaw_foundation/tests/test_cli.py` | pod runtime CLI test |
| Modify | `self_service_copilot/src/self_service_copilot/config.py` | 將 `get_pod_runtime` 加入 `supported_tools` |
| Modify | `self_service_copilot/src/self_service_copilot/bot.py` | registry 註冊 `PrometheusPodRuntimeTool` |
| Modify | `self_service_copilot/tests/test_config.py` | supported tools test |
| Modify | `self_service_copilot/tests/test_bot.py` | registry test |

---

## Task 1: Add Prometheus Adapter Skeleton

**Files:**
- Create: `openclaw_foundation/src/openclaw_foundation/adapters/prometheus.py`
- Create: `openclaw_foundation/tests/test_prometheus_adapter.py`

- [ ] **Step 1: Write the failing tests**

新增：

```python
from openclaw_foundation.adapters.prometheus import FakePrometheusProviderAdapter


def test_fake_prometheus_adapter_returns_runtime_payload() -> None:
    adapter = FakePrometheusProviderAdapter()

    result = adapter.get_pod_runtime(
        namespace="dev",
        pod_name="dev-py3-h2s-apisvc-5596c5b6bb-7hrg7",
    )

    assert result["pod_name"] == "dev-py3-h2s-apisvc-5596c5b6bb-7hrg7"
    assert result["ready"] is True
    assert result["restart_count"] == 0
    assert result["recent_restart_increase"] == 0.0
    assert result["window"] == "15m"
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd openclaw_foundation && .venv/bin/pytest tests/test_prometheus_adapter.py::test_fake_prometheus_adapter_returns_runtime_payload -q
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement**

建立 `prometheus.py`，第一版至少包含：

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class PrometheusError(RuntimeError):
    pass


class PrometheusQueryError(PrometheusError):
    pass


class PrometheusProviderAdapter(Protocol):
    def get_pod_runtime(self, namespace: str, pod_name: str) -> dict[str, object]: ...


class FakePrometheusProviderAdapter:
    def get_pod_runtime(self, namespace: str, pod_name: str) -> dict[str, object]:
        return {
            "namespace": namespace,
            "pod_name": pod_name,
            "ready": True,
            "restart_count": 0,
            "recent_restart_increase": 0.0,
            "window": "15m",
        }
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd openclaw_foundation && .venv/bin/pytest tests/test_prometheus_adapter.py::test_fake_prometheus_adapter_returns_runtime_payload -q
```

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/adapters/prometheus.py openclaw_foundation/tests/test_prometheus_adapter.py
git commit -m "feat: add prometheus adapter skeleton for pod runtime"
```

---

## Task 2: Add `PrometheusPodRuntimeTool`

**Files:**
- Create: `openclaw_foundation/src/openclaw_foundation/tools/prometheus_pod_runtime.py`
- Create: `openclaw_foundation/tests/test_prometheus_pod_runtime_tool.py`

- [ ] **Step 1: Write the failing tests**

新增：

```python
import pytest

from openclaw_foundation.adapters.prometheus import FakePrometheusProviderAdapter
from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.tools.prometheus_pod_runtime import PrometheusPodRuntimeTool


def make_request(namespace: str = "dev") -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-pod-runtime-001",
        source_product="self_service_copilot",
        scope={"environment": "staging", "cluster": "staging-main"},
        input_ref="fixture:pod-runtime",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=15,
            max_output_tokens=256,
        ),
        tool_name="get_pod_runtime",
        target={
            "cluster": "staging-main",
            "namespace": namespace,
            "resource_name": "dev-py3-h2s-apisvc-5596c5b6bb-7hrg7",
        },
    )


def test_get_pod_runtime_tool_returns_stable_summary() -> None:
    tool = PrometheusPodRuntimeTool(
        adapter=FakePrometheusProviderAdapter(),
        allowed_namespaces={"dev"},
    )

    result = tool.invoke(make_request())

    assert "runtime looks stable" in result.summary
    assert result.evidence[0]["ready"] is True


def test_get_pod_runtime_tool_denies_namespace_outside_allowlist() -> None:
    tool = PrometheusPodRuntimeTool(
        adapter=FakePrometheusProviderAdapter(),
        allowed_namespaces={"payments"},
    )

    with pytest.raises(PermissionError, match="namespace is not allowed"):
        tool.invoke(make_request(namespace="dev"))
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd openclaw_foundation && .venv/bin/pytest tests/test_prometheus_pod_runtime_tool.py -q
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement**

建立 `prometheus_pod_runtime.py`：

```python
from openclaw_foundation.adapters.prometheus import PrometheusProviderAdapter
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult


class PrometheusPodRuntimeTool:
    tool_name = "get_pod_runtime"
    supported_request_types = ("investigation",)

    def __init__(
        self,
        adapter: PrometheusProviderAdapter,
        allowed_namespaces: set[str],
    ) -> None:
        self._adapter = adapter
        self._allowed_namespaces = allowed_namespaces

    def invoke(self, request: InvestigationRequest) -> ToolResult:
        if request.target is None:
            raise ValueError("target is required for get_pod_runtime")

        namespace = request.target["namespace"]
        pod_name = request.target.get("resource_name") or request.target.get("pod_name")
        if pod_name is None:
            raise ValueError("resource_name or pod_name is required for get_pod_runtime")
        if namespace not in self._allowed_namespaces:
            raise PermissionError("namespace is not allowed")

        payload = self._adapter.get_pod_runtime(namespace, pod_name)
        ready = payload["ready"]
        recent_restart_increase = payload["recent_restart_increase"]
        state = "stable" if ready and recent_restart_increase == 0 else "unstable"
        readiness = "ready" if ready else "not ready"

        return ToolResult(
            summary=f"pod {pod_name} runtime looks {state}: {readiness}, {recent_restart_increase:g} restarts in {payload['window']}",
            evidence=[payload],
        )
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd openclaw_foundation && .venv/bin/pytest tests/test_prometheus_pod_runtime_tool.py -q
```

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/tools/prometheus_pod_runtime.py openclaw_foundation/tests/test_prometheus_pod_runtime_tool.py
git commit -m "feat: add prometheus pod runtime tool"
```

---

## Task 3: Add Real Prometheus Query Implementation

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/adapters/prometheus.py`
- Modify: `openclaw_foundation/tests/test_prometheus_adapter.py`

- [ ] **Step 1: Write the failing tests**

新增一個 fake HTTP response 測試，驗證 adapter 會做三個 query 並回固定 payload。

- [ ] **Step 2: Run to verify it fails**

Expected: `FAILED`

- [ ] **Step 3: Implement**

在 `prometheus.py` 新增：

- `RealPrometheusProviderAdapter`
- `query_instant(query: str) -> dict`
- `get_pod_runtime(namespace, pod_name)`

第一版固定 query：

```promql
kube_pod_status_ready{namespace="<ns>",pod="<pod>",condition="true"}
kube_pod_container_status_restarts_total{namespace="<ns>",pod="<pod>"}
sum(increase(kube_pod_container_status_restarts_total{namespace="<ns>",pod="<pod>"}[15m]))
```

建議 constructor：

```python
class RealPrometheusProviderAdapter:
    def __init__(self, base_url: str, timeout_seconds: int = 10) -> None:
        ...
```

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Commit**

---

## Task 4: CLI Wiring

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/cli.py`
- Create: `openclaw_foundation/fixtures/pod_runtime_request.json`
- Modify: `openclaw_foundation/tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

新增 CLI fixture test：

```python
def test_main_with_pod_runtime_fixture_prints_success_response(capsys) -> None:
    exit_code = main(
        [
            "--fixture",
            "openclaw_foundation/fixtures/pod_runtime_request.json",
            "--provider",
            "fake",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"result_state": "success"' in captured.out
    assert "get_pod_runtime" in captured.out
```

- [ ] **Step 2: Run to verify it fails**

- [ ] **Step 3: Implement**

- `cli.py` 註冊 `PrometheusPodRuntimeTool`
- fake provider 模式下建 `FakePrometheusProviderAdapter`
- `real` provider 的 Prometheus URL 先用 env，例如 `OPENCLAW_PROMETHEUS_BASE_URL`
- fixture target 用 `resource_name`

- [ ] **Step 4: Run to verify it passes**

- [ ] **Step 5: Commit**

---

## Task 5: `Self-Service Ops Copilot` Wiring

**Files:**
- Modify: `self_service_copilot/src/self_service_copilot/config.py`
- Modify: `self_service_copilot/src/self_service_copilot/bot.py`
- Modify: `self_service_copilot/tests/test_config.py`
- Modify: `self_service_copilot/tests/test_bot.py`

- [ ] **Step 1: Write the failing tests**

- `supported_tools` 包含 `get_pod_runtime`
- `build_registry()` 會註冊 `get_pod_runtime`

- [ ] **Step 2: Run to verify they fail**

- [ ] **Step 3: Implement**

- `config.py` 的 supported tools 加 `get_pod_runtime`
- `bot.py` registry 註冊 `PrometheusPodRuntimeTool`
- bot env 先額外讀 `OPENCLAW_PROMETHEUS_BASE_URL` 給 real adapter

- [ ] **Step 4: Run to verify they pass**

- [ ] **Step 5: Commit**

---

## Verification Checklist

- [ ] 不接受 raw PromQL
- [ ] `get_pod_runtime` 固定查 `ready` / `restart` / `15m increase`
- [ ] summary 為 bounded plain text
- [ ] CLI 可跑 fake fixture
- [ ] Slack grammar 不需修改
- [ ] `Self-Service Ops Copilot` 可註冊此 tool
