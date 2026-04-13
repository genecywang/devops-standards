# OpenClaw Kubernetes Error Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為真實 Kubernetes provider 建立可重用的 domain error model，並讓 CLI 對常見錯誤顯示清楚的摘要與 next-step 提示。

**Architecture:** 在 `adapters/kubernetes.py` 內建立集中式 error hierarchy 與底層例外映射，讓 `RealKubernetesProviderAdapter` 將 transport / API 錯誤轉成 platform-level semantics。CLI 只依賴 domain error 類型與訊息渲染，不直接理解底層 Kubernetes / urllib3 例外細節。

**Tech Stack:** Python 3.11、`kubernetes` Python client、pytest、既有 `openclaw_foundation` package

---

## File Structure

- Modify: `openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py`
  - 新增 error hierarchy 與真實 adapter error mapping
- Modify: `openclaw_foundation/src/openclaw_foundation/cli.py`
  - 新增 CLI error rendering 與 non-zero exit handling
- Modify: `openclaw_foundation/tests/test_kubernetes_adapter.py`
  - 覆蓋 endpoint / access denied / not found / generic failure mapping
- Modify: `openclaw_foundation/tests/test_cli.py`
  - 覆蓋 CLI 對 domain error 的輸出與 exit code

### Task 1: Add Kubernetes Error Hierarchy

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py`
- Modify: `openclaw_foundation/tests/test_kubernetes_adapter.py`

- [ ] **Step 1: Write the failing test for hierarchy relationships**

在 `openclaw_foundation/tests/test_kubernetes_adapter.py` 追加：

```python
from openclaw_foundation.adapters.kubernetes import (
    KubernetesAccessDeniedError,
    KubernetesApiError,
    KubernetesConfigError,
    KubernetesEndpointUnreachableError,
    KubernetesError,
    KubernetesResourceNotFoundError,
)


def test_kubernetes_domain_errors_share_common_base() -> None:
    assert issubclass(KubernetesConfigError, KubernetesError)
    assert issubclass(KubernetesEndpointUnreachableError, KubernetesError)
    assert issubclass(KubernetesAccessDeniedError, KubernetesError)
    assert issubclass(KubernetesResourceNotFoundError, KubernetesError)
    assert issubclass(KubernetesApiError, KubernetesError)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_kubernetes_adapter.py::test_kubernetes_domain_errors_share_common_base -q`

Expected: FAIL，因為 `KubernetesError`、`KubernetesEndpointUnreachableError`、`KubernetesAccessDeniedError`、`KubernetesResourceNotFoundError` 尚未存在。

- [ ] **Step 3: Write the minimal implementation**

在 `openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py` 調整錯誤類別：

```python
class KubernetesError(RuntimeError):
    pass


class KubernetesConfigError(KubernetesError):
    pass


class KubernetesEndpointUnreachableError(KubernetesError):
    pass


class KubernetesAccessDeniedError(KubernetesError):
    pass


class KubernetesResourceNotFoundError(KubernetesError):
    pass


class KubernetesApiError(KubernetesError):
    pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_kubernetes_adapter.py::test_kubernetes_domain_errors_share_common_base -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py openclaw_foundation/tests/test_kubernetes_adapter.py
git commit -m "feat: add kubernetes error hierarchy"
```

### Task 2: Map Real Adapter Failures to Domain Errors

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py`
- Modify: `openclaw_foundation/tests/test_kubernetes_adapter.py`

- [ ] **Step 1: Write the failing tests for endpoint, access denied, and not found**

在 `openclaw_foundation/tests/test_kubernetes_adapter.py` 追加：

```python
from kubernetes.client import ApiException
from urllib3.exceptions import NameResolutionError

from openclaw_foundation.adapters.kubernetes import (
    KubernetesAccessDeniedError,
    KubernetesEndpointUnreachableError,
    KubernetesResourceNotFoundError,
)


def test_real_adapter_maps_name_resolution_error_to_endpoint_unreachable() -> None:
    api = Mock()
    api.read_namespaced_pod_status.side_effect = NameResolutionError(
        "example.invalid",
        object(),
        OSError("dns failed"),
    )

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesEndpointUnreachableError, match="cluster endpoint unreachable"):
        adapter.get_pod_status(
            cluster="staging-main",
            namespace="payments",
            pod_name="payments-api-123",
        )


def test_real_adapter_maps_403_to_access_denied() -> None:
    api = Mock()
    api.read_namespaced_pod_status.side_effect = ApiException(status=403, reason="Forbidden")

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesAccessDeniedError, match="kubernetes access denied"):
        adapter.get_pod_status(
            cluster="staging-main",
            namespace="payments",
            pod_name="payments-api-123",
        )


def test_real_adapter_maps_404_to_resource_not_found() -> None:
    api = Mock()
    api.read_namespaced_pod_status.side_effect = ApiException(status=404, reason="Not Found")

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesResourceNotFoundError, match="pod not found"):
        adapter.get_pod_status(
            cluster="staging-main",
            namespace="payments",
            pod_name="payments-api-123",
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_kubernetes_adapter.py::test_real_adapter_maps_name_resolution_error_to_endpoint_unreachable openclaw_foundation/tests/test_kubernetes_adapter.py::test_real_adapter_maps_403_to_access_denied openclaw_foundation/tests/test_kubernetes_adapter.py::test_real_adapter_maps_404_to_resource_not_found -q`

Expected: FAIL，因為目前 `RealKubernetesProviderAdapter` 還只會拋 generic `KubernetesApiError`。

- [ ] **Step 3: Write the minimal implementation**

在 `openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py` 加入對底層例外的映射：

```python
from kubernetes.client import ApiException
from urllib3.exceptions import ConnectTimeoutError, MaxRetryError, NameResolutionError
```

並在 `RealKubernetesProviderAdapter.get_pod_status()` 內改成：

```python
        except ApiException as error:
            if error.status in (401, 403):
                raise KubernetesAccessDeniedError("kubernetes access denied") from error
            if error.status == 404:
                raise KubernetesResourceNotFoundError("pod not found") from error
            raise KubernetesApiError("failed to read pod status") from error
        except (NameResolutionError, ConnectTimeoutError, MaxRetryError) as error:
            raise KubernetesEndpointUnreachableError("cluster endpoint unreachable") from error
        except Exception as error:
            raise KubernetesApiError("failed to read pod status") from error
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_kubernetes_adapter.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py openclaw_foundation/tests/test_kubernetes_adapter.py
git commit -m "feat: map kubernetes adapter failures to domain errors"
```

### Task 3: Render Domain Errors in CLI

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/cli.py`
- Modify: `openclaw_foundation/tests/test_cli.py`

- [ ] **Step 1: Write the failing tests for CLI error rendering**

在 `openclaw_foundation/tests/test_cli.py` 追加：

```python
from openclaw_foundation.adapters.kubernetes import (
    KubernetesAccessDeniedError,
    KubernetesConfigError,
    KubernetesEndpointUnreachableError,
    KubernetesResourceNotFoundError,
)


def test_main_renders_config_error_message(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        "openclaw_foundation.cli.build_provider_adapter",
        lambda provider: (_ for _ in ()).throw(KubernetesConfigError("kubernetes config unavailable")),
    )

    exit_code = main(
        [
            "--fixture",
            "openclaw_foundation/fixtures/investigation_request.json",
            "--provider",
            "real",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "kubernetes config unavailable" in captured.err
    assert "verify in-cluster identity or kubeconfig context" in captured.err


def test_main_renders_endpoint_error_message(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        "openclaw_foundation.cli.build_provider_adapter",
        lambda provider: (_ for _ in ()).throw(KubernetesEndpointUnreachableError("cluster endpoint unreachable")),
    )

    exit_code = main(
        [
            "--fixture",
            "openclaw_foundation/fixtures/investigation_request.json",
            "--provider",
            "real",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "cluster endpoint unreachable" in captured.err
    assert "verify DNS, network path, VPN, or cluster endpoint" in captured.err


def test_main_renders_access_denied_message(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        "openclaw_foundation.cli.build_provider_adapter",
        lambda provider: (_ for _ in ()).throw(KubernetesAccessDeniedError("kubernetes access denied")),
    )

    exit_code = main(
        [
            "--fixture",
            "openclaw_foundation/fixtures/investigation_request.json",
            "--provider",
            "real",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "kubernetes access denied" in captured.err
    assert "verify service account, IAM / RBAC permissions" in captured.err


def test_main_renders_not_found_message(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        "openclaw_foundation.cli.build_provider_adapter",
        lambda provider: (_ for _ in ()).throw(KubernetesResourceNotFoundError("pod not found")),
    )

    exit_code = main(
        [
            "--fixture",
            "openclaw_foundation/fixtures/investigation_request.json",
            "--provider",
            "real",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "pod not found" in captured.err
    assert "verify cluster, namespace, and pod_name" in captured.err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_cli.py -q`

Expected: FAIL，因為目前 `main()` 會直接把例外往外丟，不會做 CLI 錯誤渲染。

- [ ] **Step 3: Write the minimal implementation**

在 `openclaw_foundation/src/openclaw_foundation/cli.py` 加入錯誤渲染 helper：

```python
import sys

from openclaw_foundation.adapters.kubernetes import (
    KubernetesAccessDeniedError,
    KubernetesConfigError,
    KubernetesEndpointUnreachableError,
    KubernetesError,
    KubernetesResourceNotFoundError,
)


def render_kubernetes_error(error: KubernetesError) -> str:
    if isinstance(error, KubernetesConfigError):
        next_check = "verify in-cluster identity or kubeconfig context"
    elif isinstance(error, KubernetesEndpointUnreachableError):
        next_check = "verify DNS, network path, VPN, or cluster endpoint"
    elif isinstance(error, KubernetesAccessDeniedError):
        next_check = "verify service account, IAM / RBAC permissions"
    elif isinstance(error, KubernetesResourceNotFoundError):
        next_check = "verify cluster, namespace, and pod_name"
    else:
        next_check = "inspect kubernetes client error details"
    return f"{error}\nnext check: {next_check}"
```

並在 `main()` 內用：

```python
    try:
        provider_adapter = build_provider_adapter(args.provider)
        ...
        response = OpenClawRunner(registry).run(request)
    except KubernetesError as error:
        print(render_kubernetes_error(error), file=sys.stderr)
        return 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_cli.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/cli.py openclaw_foundation/tests/test_cli.py
git commit -m "feat: render kubernetes domain errors in cli"
```

### Task 4: Verify End-to-End Failure Rendering

**Files:**
- Modify: `openclaw_foundation/tests/test_cli.py`
- Test: `openclaw_foundation/tests/test_kubernetes_adapter.py`
- Test: `openclaw_foundation/tests/test_cli.py`

- [ ] **Step 1: Write the failing subprocess test for real-provider stderr output**

在 `openclaw_foundation/tests/test_cli.py` 追加：

```python
def test_cli_subprocess_surfaces_readable_real_provider_error() -> None:
    project_root = Path(__file__).resolve().parents[1]
    env = {
        "PYTHONPATH": str(project_root / "src"),
    }

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "openclaw_foundation.cli",
            "--fixture",
            str(project_root / "fixtures" / "investigation_request.json"),
            "--provider",
            "real",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 1
    assert "next check:" in completed.stderr
```

- [ ] **Step 2: Run test to verify the current failure mode**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests/test_cli.py::test_cli_subprocess_surfaces_readable_real_provider_error -q`

Expected: FAIL，若 subprocess 仍輸出 raw traceback 或沒有 `next check:`。

- [ ] **Step 3: Finalize error rendering and keep fake flow intact**

確認：

- `fake` provider path 仍回傳 exit code `0`
- `real` provider path 對 domain error 回傳 exit code `1`
- stderr 使用 `render_kubernetes_error()` 格式

保留既有 success smoke test：

```python
assert payload["request_id"] == "req-001"
assert payload["result_state"] == "success"
assert "payments-api-123" in payload["summary"]
```

- [ ] **Step 4: Run full verification**

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests -q`
Expected: PASS

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m openclaw_foundation.cli --fixture openclaw_foundation/fixtures/investigation_request.json --provider fake`
Expected: JSON output with `"result_state": "success"`

Run: `PYTHONPATH=openclaw_foundation/src openclaw_foundation/.venv/bin/python -m openclaw_foundation.cli --fixture openclaw_foundation/fixtures/investigation_request.json --provider real`
Expected: non-zero exit，stderr 含有 domain-level message 與 `next check:`

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py openclaw_foundation/src/openclaw_foundation/cli.py openclaw_foundation/tests/test_kubernetes_adapter.py openclaw_foundation/tests/test_cli.py
git commit -m "test: verify kubernetes error rendering"
```
