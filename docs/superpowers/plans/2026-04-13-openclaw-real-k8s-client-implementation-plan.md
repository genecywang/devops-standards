# OpenClaw Real Kubernetes Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為既有 `get_pod_status` tool 接入真實 Kubernetes client，支援 `in-cluster` 與 `local kubeconfig`，同時保留目前 fake provider 的可測試路徑。

**Architecture:** 保持既有 `tool -> adapter -> provider` 邊界，將 config loading 收斂在 `adapters/kubernetes.py` 的 client factory，讓 `RealKubernetesProviderAdapter` 只處理 CoreV1 API 呼叫與 bounded payload 轉換。CLI 只負責 provider mode 組裝，不處理 Kubernetes config semantics。

**Tech Stack:** Python 3.11、`kubernetes` Python client、pytest、既有 `openclaw_foundation` package

---

## File Structure

- Modify: `openclaw_foundation/pyproject.toml`
  - 加入 `kubernetes` runtime dependency
- Modify: `openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py`
  - 新增 domain error、client factory、真實 adapter
- Modify: `openclaw_foundation/src/openclaw_foundation/cli.py`
  - 新增 `--provider` mode 與 real provider wiring
- Modify: `openclaw_foundation/src/openclaw_foundation/tools/kubernetes_pod_status.py`
  - 保持介面穩定，只在需要時對 adapter 型別擴充
- Add: `openclaw_foundation/tests/test_kubernetes_adapter.py`
  - 覆蓋 client factory 與真實 adapter payload mapping
- Modify: `openclaw_foundation/tests/test_cli.py`
  - 覆蓋 `fake` / `real` provider mode 與錯誤路徑

### Task 1: Add Kubernetes Dependency

**Files:**
- Modify: `openclaw_foundation/pyproject.toml`
- Test: `openclaw_foundation/tests/test_cli.py`

- [ ] **Step 1: Write the failing dependency expectation**

在 `openclaw_foundation/tests/test_cli.py` 新增一個 import-level smoke test，確認 CLI module 可引用 real provider factory symbol：

```python
from openclaw_foundation.cli import build_provider_adapter


def test_build_provider_adapter_is_importable() -> None:
    assert callable(build_provider_adapter)
```

- [ ] **Step 2: Run test to verify the current failure mode**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_cli.py::test_build_provider_adapter_is_importable -q`

Expected: FAIL，因為 `build_provider_adapter` 尚未存在。

- [ ] **Step 3: Add runtime dependency**

更新 `openclaw_foundation/pyproject.toml`：

```toml
[project]
name = "openclaw-foundation"
version = "0.1.0"
description = "Minimal executable OpenClaw foundation skeleton"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "kubernetes>=30.0.0,<31.0.0",
]
```

- [ ] **Step 4: Run the targeted test again after later CLI wiring lands**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_cli.py::test_build_provider_adapter_is_importable -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/pyproject.toml openclaw_foundation/tests/test_cli.py
git commit -m "build: add kubernetes client dependency"
```

### Task 2: Add Client Factory and Domain Errors

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py`
- Test: `openclaw_foundation/tests/test_kubernetes_adapter.py`

- [ ] **Step 1: Write the failing tests for config loading order**

建立 `openclaw_foundation/tests/test_kubernetes_adapter.py`：

```python
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from openclaw_foundation.adapters.kubernetes import (
    KubernetesConfigError,
    build_core_v1_api,
)


def test_build_core_v1_api_uses_incluster_first(monkeypatch: pytest.MonkeyPatch) -> None:
    load_incluster_config = Mock()
    load_kube_config = Mock()
    core_v1_api = Mock(return_value="core-v1")

    monkeypatch.setattr(
        "openclaw_foundation.adapters.kubernetes.kube_config",
        SimpleNamespace(
            load_incluster_config=load_incluster_config,
            load_kube_config=load_kube_config,
        ),
    )
    monkeypatch.setattr(
        "openclaw_foundation.adapters.kubernetes.client",
        SimpleNamespace(CoreV1Api=core_v1_api),
    )

    result = build_core_v1_api()

    assert result == "core-v1"
    load_incluster_config.assert_called_once_with()
    load_kube_config.assert_not_called()


def test_build_core_v1_api_falls_back_to_kubeconfig(monkeypatch: pytest.MonkeyPatch) -> None:
    load_incluster_config = Mock(side_effect=RuntimeError("no serviceaccount"))
    load_kube_config = Mock()
    core_v1_api = Mock(return_value="core-v1")

    monkeypatch.setattr(
        "openclaw_foundation.adapters.kubernetes.kube_config",
        SimpleNamespace(
            load_incluster_config=load_incluster_config,
            load_kube_config=load_kube_config,
        ),
    )
    monkeypatch.setattr(
        "openclaw_foundation.adapters.kubernetes.client",
        SimpleNamespace(CoreV1Api=core_v1_api),
    )

    result = build_core_v1_api()

    assert result == "core-v1"
    load_incluster_config.assert_called_once_with()
    load_kube_config.assert_called_once_with()


def test_build_core_v1_api_raises_config_error_when_no_loader_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "openclaw_foundation.adapters.kubernetes.kube_config",
        SimpleNamespace(
            load_incluster_config=Mock(side_effect=RuntimeError("no serviceaccount")),
            load_kube_config=Mock(side_effect=RuntimeError("no kubeconfig")),
        ),
    )

    with pytest.raises(KubernetesConfigError, match="unable to load kubernetes config"):
        build_core_v1_api()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_kubernetes_adapter.py -q`

Expected: FAIL，因為 `KubernetesConfigError` 與 `build_core_v1_api` 尚未存在。

- [ ] **Step 3: Write the minimal implementation**

在 `openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py` 加入：

```python
from typing import Protocol

from kubernetes import client, config as kube_config


class KubernetesConfigError(RuntimeError):
    pass


class KubernetesApiError(RuntimeError):
    pass


class KubernetesProviderAdapter(Protocol):
    def get_pod_status(self, cluster: str, namespace: str, pod_name: str) -> dict[str, object]: ...


def build_core_v1_api() -> client.CoreV1Api:
    try:
        kube_config.load_incluster_config()
    except Exception as incluster_error:
        try:
            kube_config.load_kube_config()
        except Exception as kubeconfig_error:
            raise KubernetesConfigError("unable to load kubernetes config") from kubeconfig_error
    return client.CoreV1Api()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_kubernetes_adapter.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py openclaw_foundation/tests/test_kubernetes_adapter.py
git commit -m "feat: add kubernetes client factory"
```

### Task 3: Implement Real Kubernetes Provider Adapter

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py`
- Test: `openclaw_foundation/tests/test_kubernetes_adapter.py`

- [ ] **Step 1: Write the failing tests for payload mapping and not found handling**

在 `openclaw_foundation/tests/test_kubernetes_adapter.py` 追加：

```python
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from openclaw_foundation.adapters.kubernetes import KubernetesApiError, RealKubernetesProviderAdapter


def test_real_adapter_maps_pod_status_payload() -> None:
    api = Mock()
    api.read_namespaced_pod_status.return_value = SimpleNamespace(
        metadata=SimpleNamespace(name="payments-api-123"),
        status=SimpleNamespace(
            phase="Running",
            container_statuses=[
                SimpleNamespace(
                    name="app",
                    ready=True,
                    image="example:v1",
                )
            ],
        ),
        spec=SimpleNamespace(node_name="node-a"),
    )

    adapter = RealKubernetesProviderAdapter(api)

    result = adapter.get_pod_status(
        cluster="staging-main",
        namespace="payments",
        pod_name="payments-api-123",
    )

    assert result == {
        "pod_name": "payments-api-123",
        "namespace": "payments",
        "phase": "Running",
        "container_statuses": [{"name": "app", "ready": True, "image": "example:v1"}],
        "node_name": "node-a",
    }


def test_real_adapter_raises_domain_error_on_api_failure() -> None:
    api = Mock()
    api.read_namespaced_pod_status.side_effect = RuntimeError("boom")

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesApiError, match="failed to read pod status"):
        adapter.get_pod_status(
            cluster="staging-main",
            namespace="payments",
            pod_name="payments-api-123",
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_kubernetes_adapter.py::test_real_adapter_maps_pod_status_payload openclaw_foundation/tests/test_kubernetes_adapter.py::test_real_adapter_raises_domain_error_on_api_failure -q`

Expected: FAIL，因為 `RealKubernetesProviderAdapter` 尚未存在。

- [ ] **Step 3: Write the minimal implementation**

在 `openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py` 追加：

```python
class RealKubernetesProviderAdapter:
    def __init__(self, core_v1_api: client.CoreV1Api) -> None:
        self._core_v1_api = core_v1_api

    def get_pod_status(self, cluster: str, namespace: str, pod_name: str) -> dict[str, object]:
        try:
            pod = self._core_v1_api.read_namespaced_pod_status(name=pod_name, namespace=namespace)
        except Exception as error:
            raise KubernetesApiError("failed to read pod status") from error

        statuses = []
        for container_status in getattr(pod.status, "container_statuses", []) or []:
            statuses.append(
                {
                    "name": container_status.name,
                    "ready": container_status.ready,
                    "image": getattr(container_status, "image", None),
                }
            )

        return {
            "pod_name": pod.metadata.name,
            "namespace": namespace,
            "phase": pod.status.phase,
            "container_statuses": statuses,
            "node_name": getattr(pod.spec, "node_name", None),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_kubernetes_adapter.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py openclaw_foundation/tests/test_kubernetes_adapter.py
git commit -m "feat: add real kubernetes provider adapter"
```

### Task 4: Wire CLI Provider Mode

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/cli.py`
- Test: `openclaw_foundation/tests/test_cli.py`

- [ ] **Step 1: Write the failing tests for provider selection**

在 `openclaw_foundation/tests/test_cli.py` 追加：

```python
from unittest.mock import Mock

import pytest

from openclaw_foundation.adapters.kubernetes import FakeKubernetesProviderAdapter
from openclaw_foundation.cli import build_provider_adapter, parse_args


def test_parse_args_defaults_provider_to_fake() -> None:
    args = parse_args(["--fixture", "openclaw_foundation/fixtures/investigation_request.json"])
    assert args.provider == "fake"


def test_build_provider_adapter_returns_fake_provider() -> None:
    adapter = build_provider_adapter("fake")
    assert isinstance(adapter, FakeKubernetesProviderAdapter)


def test_build_provider_adapter_returns_real_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_factory = Mock(return_value="core-v1")
    fake_adapter = Mock(return_value="real-adapter")

    monkeypatch.setattr("openclaw_foundation.cli.build_core_v1_api", fake_factory)
    monkeypatch.setattr("openclaw_foundation.cli.RealKubernetesProviderAdapter", fake_adapter)

    result = build_provider_adapter("real")

    assert result == "real-adapter"
    fake_factory.assert_called_once_with()
    fake_adapter.assert_called_once_with("core-v1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_cli.py -q`

Expected: FAIL，因為 `parse_args` 與 `build_provider_adapter` 尚未支援 `provider` mode。

- [ ] **Step 3: Write the minimal implementation**

在 `openclaw_foundation/src/openclaw_foundation/cli.py` 讓 CLI 支援：

```python
import argparse

from openclaw_foundation.adapters.kubernetes import (
    FakeKubernetesProviderAdapter,
    RealKubernetesProviderAdapter,
    build_core_v1_api,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--provider", choices=("fake", "real"), default="fake")
    return parser.parse_args(argv)


def build_provider_adapter(provider: str):
    if provider == "fake":
        return FakeKubernetesProviderAdapter()
    if provider == "real":
        return RealKubernetesProviderAdapter(build_core_v1_api())
    raise ValueError(f"unsupported provider mode: {provider}")
```

並在 `main()` 內改用：

```python
args = parse_args(argv)
provider_adapter = build_provider_adapter(args.provider)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_cli.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/cli.py openclaw_foundation/tests/test_cli.py
git commit -m "feat: add cli provider mode for kubernetes"
```

### Task 5: Verify End-to-End Behavior

**Files:**
- Modify: `openclaw_foundation/tests/test_cli.py`
- Test: `openclaw_foundation/tests/test_cli.py`
- Test: `openclaw_foundation/tests/test_kubernetes_adapter.py`

- [ ] **Step 1: Write the failing CLI real-provider error-path test**

在 `openclaw_foundation/tests/test_cli.py` 追加：

```python
import pytest

from openclaw_foundation.adapters.kubernetes import KubernetesConfigError
from openclaw_foundation.cli import main


def test_main_propagates_real_provider_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "openclaw_foundation.cli.build_provider_adapter",
        lambda provider: (_ for _ in ()).throw(KubernetesConfigError("unable to load kubernetes config")),
    )

    with pytest.raises(KubernetesConfigError, match="unable to load kubernetes config"):
        main(
            [
                "--fixture",
                "openclaw_foundation/fixtures/investigation_request.json",
                "--provider",
                "real",
            ]
        )
```

- [ ] **Step 2: Run test to verify it fails if error handling is not correctly wired**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_cli.py::test_main_propagates_real_provider_config_error -q`

Expected: FAIL，若 `main()` 尚未透過 `build_provider_adapter(args.provider)` 建立 provider。

- [ ] **Step 3: Finalize wiring and keep fake flow intact**

確認 `main()` 內註冊 Kubernetes tool 時使用：

```python
provider_adapter = build_provider_adapter(args.provider)
registry.register(
    KubernetesPodStatusTool(
        adapter=provider_adapter,
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
    )
)
```

並保留既有 fake CLI smoke test，可繼續驗證輸出包含：

```python
assert payload["result_state"] == "success"
assert payload["summary"] == "pod payments-api-123 is Running"
```

- [ ] **Step 4: Run full verification**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests -q`
Expected: PASS

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m openclaw_foundation.cli --fixture openclaw_foundation/fixtures/investigation_request.json --provider fake`
Expected: JSON output with `"result_state": "success"`

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/cli.py openclaw_foundation/tests/test_cli.py openclaw_foundation/tests/test_kubernetes_adapter.py
git commit -m "test: verify real kubernetes provider wiring"
```
