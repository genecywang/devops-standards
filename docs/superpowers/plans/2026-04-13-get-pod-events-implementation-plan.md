# get_pod_events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在既有 adapter / guardrail / error model 邊界上，新增第二個 read-only Kubernetes tool：`get_pod_events`。

**Architecture:** 沿用 Adapter-first 架構，先在 `KubernetesProviderAdapter` Protocol、`FakeKubernetesProviderAdapter`、`RealKubernetesProviderAdapter` 各自加入 `get_pod_events`，再建立 `KubernetesPodEventsTool`，最後在 CLI 註冊。Guardrail 層新增 `truncate_pod_events`（限 10 筆、訊息截到 256 字元），redaction 沿用現有 `redact_output`。

**Tech Stack:** Python 3.12, kubernetes-client, pytest, 既有 `openclaw_foundation` 內部 models / guards / runtime。

---

## File Map

| 操作 | 路徑 | 變更說明 |
|------|------|----------|
| Modify | `openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py` | Protocol + Fake + Real 各加 `get_pod_events` |
| Modify | `openclaw_foundation/src/openclaw_foundation/runtime/guards.py` | 加 `truncate_pod_events` |
| Create | `openclaw_foundation/src/openclaw_foundation/tools/kubernetes_pod_events.py` | `KubernetesPodEventsTool` |
| Modify | `openclaw_foundation/src/openclaw_foundation/cli.py` | 引入並註冊 `KubernetesPodEventsTool` |
| Create | `openclaw_foundation/fixtures/pod_events_request.json` | CLI 子程序測試用 fixture |
| Modify | `openclaw_foundation/tests/test_kubernetes_adapter.py` | Fake + Real `get_pod_events` 測試 |
| Modify | `openclaw_foundation/tests/test_runtime_guards.py` | `truncate_pod_events` 測試 |
| Create | `openclaw_foundation/tests/test_kubernetes_pod_events_tool.py` | `KubernetesPodEventsTool` 測試 |
| Modify | `openclaw_foundation/tests/test_cli.py` | Events fixture 的 CLI 子程序測試 |

---

## Task 1: Extend Protocol + Fake Adapter with `get_pod_events`

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py`
- Modify: `openclaw_foundation/tests/test_kubernetes_adapter.py`

- [ ] **Step 1: Write the failing test** (in `test_kubernetes_adapter.py`)

```python
from openclaw_foundation.adapters.kubernetes import FakeKubernetesProviderAdapter


def test_fake_adapter_get_pod_events_returns_bounded_event_list() -> None:
    adapter = FakeKubernetesProviderAdapter()

    result = adapter.get_pod_events(
        cluster="staging-main",
        namespace="payments",
        pod_name="payments-api-123",
    )

    assert isinstance(result, list)
    assert len(result) >= 1
    first = result[0]
    assert set(first.keys()) == {"type", "reason", "message", "count", "last_timestamp"}


def test_fake_adapter_get_pod_events_message_contains_redactable_content() -> None:
    adapter = FakeKubernetesProviderAdapter()

    result = adapter.get_pod_events(
        cluster="staging-main",
        namespace="payments",
        pod_name="payments-api-123",
    )

    all_messages = " ".join(str(e["message"]) for e in result)
    assert "Bearer" in all_messages
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd openclaw_foundation && python -m pytest tests/test_kubernetes_adapter.py::test_fake_adapter_get_pod_events_returns_bounded_event_list tests/test_kubernetes_adapter.py::test_fake_adapter_get_pod_events_message_contains_redactable_content -v
```

Expected: `FAILED` — `AttributeError: 'FakeKubernetesProviderAdapter' object has no attribute 'get_pod_events'`

- [ ] **Step 3: Implement** — extend Protocol and add to `FakeKubernetesProviderAdapter`

在 `adapters/kubernetes.py` 中：

```python
class KubernetesProviderAdapter(Protocol):
    def get_pod_status(self, cluster: str, namespace: str, pod_name: str) -> dict[str, object]: ...
    def get_pod_events(self, cluster: str, namespace: str, pod_name: str) -> list[dict[str, object]]: ...
```

在 `FakeKubernetesProviderAdapter` 中新增方法（放在 `get_pod_status` 之後）：

```python
    def get_pod_events(self, cluster: str, namespace: str, pod_name: str) -> list[dict[str, object]]:
        return [
            {
                "type": "Warning",
                "reason": "BackOff",
                "message": f"Back-off restarting failed container: Bearer secret-event-token",
                "count": 3,
                "last_timestamp": "2026-04-13T12:00:00Z",
            },
            {
                "type": "Normal",
                "reason": "Pulled",
                "message": "Successfully pulled image example:v1",
                "count": 1,
                "last_timestamp": "2026-04-13T11:55:00Z",
            },
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd openclaw_foundation && python -m pytest tests/test_kubernetes_adapter.py::test_fake_adapter_get_pod_events_returns_bounded_event_list tests/test_kubernetes_adapter.py::test_fake_adapter_get_pod_events_message_contains_redactable_content -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py openclaw_foundation/tests/test_kubernetes_adapter.py
git commit -m "feat: extend kubernetes adapter protocol and fake provider with get_pod_events"
```

---

## Task 2: Add `truncate_pod_events` Guard

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/runtime/guards.py`
- Modify: `openclaw_foundation/tests/test_runtime_guards.py`

- [ ] **Step 1: Write the failing tests** (in `test_runtime_guards.py`)

在 import block 新增 `truncate_pod_events`，然後加兩個 test：

```python
from openclaw_foundation.runtime.guards import (
    redact_output,
    truncate_pod_events,   # 新增
    truncate_pod_status,
    validate_scope,
)


def _make_event(reason: str = "Reason", message: str = "msg") -> dict:
    return {
        "type": "Normal",
        "reason": reason,
        "message": message,
        "count": 1,
        "last_timestamp": "2026-04-13T12:00:00Z",
    }


def test_truncate_pod_events_limits_list_to_ten_events() -> None:
    events = [_make_event(reason=f"R{i}") for i in range(15)]

    result = truncate_pod_events(events)

    assert len(result) == 10


def test_truncate_pod_events_truncates_message_longer_than_256_chars() -> None:
    long_msg = "x" * 300
    events = [_make_event(message=long_msg)]

    result = truncate_pod_events(events)

    assert len(result[0]["message"]) <= 270  # 256 + len("...[truncated]")
    assert result[0]["message"].endswith("...[truncated]")


def test_truncate_pod_events_preserves_short_message_unchanged() -> None:
    events = [_make_event(message="short message")]

    result = truncate_pod_events(events)

    assert result[0]["message"] == "short message"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd openclaw_foundation && python -m pytest tests/test_runtime_guards.py::test_truncate_pod_events_limits_list_to_ten_events tests/test_runtime_guards.py::test_truncate_pod_events_truncates_message_longer_than_256_chars tests/test_runtime_guards.py::test_truncate_pod_events_preserves_short_message_unchanged -v
```

Expected: `ERROR` — `ImportError: cannot import name 'truncate_pod_events'`

- [ ] **Step 3: Implement** — add `truncate_pod_events` to `guards.py`

在 `truncate_pod_status` 之後加：

```python
_MAX_EVENTS = 10
_MAX_MESSAGE_LEN = 256


def truncate_pod_events(events: list[dict[str, object]]) -> list[dict[str, object]]:
    bounded = events[:_MAX_EVENTS]
    result = []
    for event in bounded:
        entry = dict(event)
        msg = entry.get("message")
        if isinstance(msg, str) and len(msg) > _MAX_MESSAGE_LEN:
            entry["message"] = msg[:_MAX_MESSAGE_LEN] + "...[truncated]"
        result.append(entry)
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd openclaw_foundation && python -m pytest tests/test_runtime_guards.py::test_truncate_pod_events_limits_list_to_ten_events tests/test_runtime_guards.py::test_truncate_pod_events_truncates_message_longer_than_256_chars tests/test_runtime_guards.py::test_truncate_pod_events_preserves_short_message_unchanged -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/runtime/guards.py openclaw_foundation/tests/test_runtime_guards.py
git commit -m "feat: add truncate_pod_events guard with max 10 events and 256-char message limit"
```

---

## Task 3: Real Adapter `get_pod_events`

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py`
- Modify: `openclaw_foundation/tests/test_kubernetes_adapter.py`

- [ ] **Step 1: Write the failing tests**

在 `test_kubernetes_adapter.py` 尾端加：

```python
import datetime


def test_real_adapter_maps_pod_events_payload() -> None:
    api = Mock()
    ts = datetime.datetime(2026, 4, 13, 12, 0, 0, tzinfo=datetime.timezone.utc)
    api.list_namespaced_event.return_value = SimpleNamespace(
        items=[
            SimpleNamespace(
                type="Warning",
                reason="BackOff",
                message="Back-off restarting failed container",
                count=3,
                last_timestamp=ts,
            )
        ]
    )

    adapter = RealKubernetesProviderAdapter(api)
    result = adapter.get_pod_events(
        cluster="staging-main",
        namespace="payments",
        pod_name="payments-api-123",
    )

    api.list_namespaced_event.assert_called_once_with(
        namespace="payments",
        field_selector="involvedObject.name=payments-api-123",
    )
    assert result == [
        {
            "type": "Warning",
            "reason": "BackOff",
            "message": "Back-off restarting failed container",
            "count": 3,
            "last_timestamp": "2026-04-13T12:00:00+00:00",
        }
    ]


def test_real_adapter_get_pod_events_maps_none_timestamp() -> None:
    api = Mock()
    api.list_namespaced_event.return_value = SimpleNamespace(
        items=[
            SimpleNamespace(
                type="Normal",
                reason="Pulled",
                message="image pulled",
                count=1,
                last_timestamp=None,
            )
        ]
    )

    adapter = RealKubernetesProviderAdapter(api)
    result = adapter.get_pod_events(
        cluster="staging-main",
        namespace="payments",
        pod_name="payments-api-123",
    )

    assert result[0]["last_timestamp"] is None


def test_real_adapter_get_pod_events_maps_403_to_access_denied() -> None:
    api = Mock()
    api.list_namespaced_event.side_effect = ApiException(status=403, reason="Forbidden")

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesAccessDeniedError, match="kubernetes access denied"):
        adapter.get_pod_events(
            cluster="staging-main",
            namespace="payments",
            pod_name="payments-api-123",
        )


def test_real_adapter_get_pod_events_maps_404_to_resource_not_found() -> None:
    api = Mock()
    api.list_namespaced_event.side_effect = ApiException(status=404, reason="Not Found")

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesResourceNotFoundError, match="namespace not found"):
        adapter.get_pod_events(
            cluster="staging-main",
            namespace="payments",
            pod_name="payments-api-123",
        )


def test_real_adapter_get_pod_events_maps_generic_api_error() -> None:
    api = Mock()
    api.list_namespaced_event.side_effect = RuntimeError("boom")

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesApiError, match="failed to list pod events"):
        adapter.get_pod_events(
            cluster="staging-main",
            namespace="payments",
            pod_name="payments-api-123",
        )


def test_real_adapter_get_pod_events_maps_name_resolution_error() -> None:
    api = Mock()
    api.list_namespaced_event.side_effect = NameResolutionError(
        "example.invalid",
        object(),
        OSError("dns failed"),
    )

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesEndpointUnreachableError, match="cluster endpoint unreachable"):
        adapter.get_pod_events(
            cluster="staging-main",
            namespace="payments",
            pod_name="payments-api-123",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd openclaw_foundation && python -m pytest tests/test_kubernetes_adapter.py::test_real_adapter_maps_pod_events_payload tests/test_kubernetes_adapter.py::test_real_adapter_get_pod_events_maps_403_to_access_denied tests/test_kubernetes_adapter.py::test_real_adapter_get_pod_events_maps_generic_api_error -v
```

Expected: `FAILED` — `AttributeError: 'RealKubernetesProviderAdapter' object has no attribute 'get_pod_events'`

- [ ] **Step 3: Implement** — add `get_pod_events` to `RealKubernetesProviderAdapter`

在 `RealKubernetesProviderAdapter.get_pod_status` 之後加：

```python
    def get_pod_events(self, cluster: str, namespace: str, pod_name: str) -> list[dict[str, object]]:
        try:
            event_list = self._core_v1_api.list_namespaced_event(
                namespace=namespace,
                field_selector=f"involvedObject.name={pod_name}",
            )
        except ApiException as error:
            if error.status in (401, 403):
                raise KubernetesAccessDeniedError("kubernetes access denied") from error
            if error.status == 404:
                raise KubernetesResourceNotFoundError("namespace not found") from error
            raise KubernetesApiError("failed to list pod events") from error
        except (NameResolutionError, ConnectTimeoutError, MaxRetryError) as error:
            raise KubernetesEndpointUnreachableError("cluster endpoint unreachable") from error
        except Exception as error:
            raise KubernetesApiError("failed to list pod events") from error

        result = []
        for event in getattr(event_list, "items", []) or []:
            last_ts = getattr(event, "last_timestamp", None)
            result.append(
                {
                    "type": getattr(event, "type", None),
                    "reason": getattr(event, "reason", None),
                    "message": getattr(event, "message", None),
                    "count": getattr(event, "count", None),
                    "last_timestamp": last_ts.isoformat() if last_ts is not None else None,
                }
            )
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd openclaw_foundation && python -m pytest tests/test_kubernetes_adapter.py -v
```

Expected: 全部 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/adapters/kubernetes.py openclaw_foundation/tests/test_kubernetes_adapter.py
git commit -m "feat: implement get_pod_events on real kubernetes adapter with domain error mapping"
```

---

## Task 4: `KubernetesPodEventsTool`

**Files:**
- Create: `openclaw_foundation/src/openclaw_foundation/tools/kubernetes_pod_events.py`
- Create: `openclaw_foundation/tests/test_kubernetes_pod_events_tool.py`

- [ ] **Step 1: Write the failing tests** — create `test_kubernetes_pod_events_tool.py`

```python
import pytest

from openclaw_foundation.adapters.kubernetes import FakeKubernetesProviderAdapter
from openclaw_foundation.models.enums import RequestType
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.tools.kubernetes_pod_events import KubernetesPodEventsTool


def make_events_request(namespace: str = "payments") -> InvestigationRequest:
    return InvestigationRequest(
        request_type=RequestType.INVESTIGATION,
        request_id="req-k8s-events-001",
        source_product="alert_auto_investigator",
        scope={"environment": "staging", "cluster": "staging-main"},
        input_ref="fixture:k8s-events-demo",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=30,
            max_output_tokens=256,
        ),
        tool_name="get_pod_events",
        target={
            "cluster": "staging-main",
            "namespace": namespace,
            "pod_name": "payments-api-123",
        },
    )


def test_get_pod_events_tool_returns_event_list_via_adapter() -> None:
    tool = KubernetesPodEventsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
    )

    result = tool.invoke(make_events_request())

    assert "payments-api-123" in result.summary
    assert len(result.evidence) >= 1
    first = result.evidence[0]
    assert set(first.keys()) == {"type", "reason", "message", "count", "last_timestamp"}


def test_get_pod_events_tool_denies_cluster_outside_allowlist() -> None:
    tool = KubernetesPodEventsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"prod-main"},
        allowed_namespaces={"payments"},
    )

    with pytest.raises(PermissionError, match="cluster is not allowed"):
        tool.invoke(make_events_request())


def test_get_pod_events_tool_denies_namespace_outside_allowlist() -> None:
    tool = KubernetesPodEventsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"other"},
    )

    with pytest.raises(PermissionError, match="namespace is not allowed"):
        tool.invoke(make_events_request(namespace="payments"))


def test_get_pod_events_tool_redacts_bearer_token_in_message() -> None:
    tool = KubernetesPodEventsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
    )

    result = tool.invoke(make_events_request())

    all_messages = " ".join(str(e["message"]) for e in result.evidence)
    assert "secret-event-token" not in all_messages
    assert "Bearer [REDACTED]" in all_messages


def test_get_pod_events_tool_evidence_does_not_contain_raw_object() -> None:
    tool = KubernetesPodEventsTool(
        adapter=FakeKubernetesProviderAdapter(),
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
    )

    result = tool.invoke(make_events_request())

    for event in result.evidence:
        assert "raw_object" not in event
        assert "metadata" not in event
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd openclaw_foundation && python -m pytest tests/test_kubernetes_pod_events_tool.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'openclaw_foundation.tools.kubernetes_pod_events'`

- [ ] **Step 3: Implement** — create `kubernetes_pod_events.py`

```python
from openclaw_foundation.adapters.kubernetes import KubernetesProviderAdapter
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult
from openclaw_foundation.runtime.guards import redact_output, truncate_pod_events, validate_scope


class KubernetesPodEventsTool:
    tool_name = "get_pod_events"
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
            raise ValueError("target is required for get_pod_events")

        cluster = request.target["cluster"]
        namespace = request.target["namespace"]
        pod_name = request.target["pod_name"]
        validate_scope(cluster, namespace, self._allowed_clusters, self._allowed_namespaces)

        events = self._adapter.get_pod_events(cluster, namespace, pod_name)
        truncated = truncate_pod_events(events)
        redacted = [redact_output(event) for event in truncated]
        return ToolResult(
            summary=f"pod {pod_name} has {len(redacted)} recent events",
            evidence=redacted,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd openclaw_foundation && python -m pytest tests/test_kubernetes_pod_events_tool.py -v
```

Expected: 全部 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/tools/kubernetes_pod_events.py openclaw_foundation/tests/test_kubernetes_pod_events_tool.py
git commit -m "feat: add KubernetesPodEventsTool with scope validation, truncation, and redaction"
```

---

## Task 5: CLI Registration + Fixture

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/cli.py`
- Create: `openclaw_foundation/fixtures/pod_events_request.json`
- Modify: `openclaw_foundation/tests/test_cli.py`

- [ ] **Step 1: Write the failing test** — 在 `test_cli.py` 尾端加：

```python
def test_cli_outputs_success_response_for_pod_events() -> None:
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
            str(project_root / "fixtures" / "pod_events_request.json"),
        ],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )

    payload = json.loads(completed.stdout)

    assert payload["request_id"] == "req-events-001"
    assert payload["result_state"] == "success"
    assert "payments-api-123" in payload["summary"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd openclaw_foundation && python -m pytest tests/test_cli.py::test_cli_outputs_success_response_for_pod_events -v
```

Expected: `FAILED` — 找不到 `pod_events_request.json` 或 tool not found

- [ ] **Step 3a: Create fixture** — `openclaw_foundation/fixtures/pod_events_request.json`

```json
{
  "request_type": "investigation",
  "request_id": "req-events-001",
  "source_product": "alert_auto_investigator",
  "scope": {
    "environment": "staging",
    "cluster": "staging-main"
  },
  "input_ref": "fixture:k8s-events-demo",
  "tool_name": "get_pod_events",
  "target": {
    "cluster": "staging-main",
    "namespace": "payments",
    "pod_name": "payments-api-123"
  },
  "budget": {
    "max_steps": 2,
    "max_tool_calls": 1,
    "max_duration_seconds": 30,
    "max_output_tokens": 256
  }
}
```

- [ ] **Step 3b: Register tool in CLI** — 在 `cli.py` 中修改 import 和 `main`

Import block 加一行：
```python
from openclaw_foundation.tools.kubernetes_pod_events import KubernetesPodEventsTool
```

在 `registry.register(KubernetesPodStatusTool(...))` 之後加：
```python
        registry.register(
            KubernetesPodEventsTool(
                adapter=provider_adapter,
                allowed_clusters={"staging-main"},
                allowed_namespaces={"payments"},
            )
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd openclaw_foundation && python -m pytest tests/test_cli.py::test_cli_outputs_success_response_for_pod_events -v
```

Expected: `PASSED`

- [ ] **Step 5: Run full test suite to verify no regressions**

```bash
cd openclaw_foundation && python -m pytest tests/ -v
```

Expected: 全部 `PASSED`

- [ ] **Step 6: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/cli.py openclaw_foundation/fixtures/pod_events_request.json openclaw_foundation/tests/test_cli.py
git commit -m "feat: register KubernetesPodEventsTool in CLI and add pod events fixture"
```

---

## Spec Coverage Check

| Spec requirement | Covered by |
|---|---|
| `KubernetesProviderAdapter.get_pod_events` 加入 Protocol | Task 1 Step 3 |
| `FakeKubernetesProviderAdapter.get_pod_events` | Task 1 Step 3 |
| `RealKubernetesProviderAdapter.get_pod_events` via `list_namespaced_event` | Task 3 Step 3 |
| Bounded payload (`type`, `reason`, `message`, `count`, `last_timestamp`) | Task 3 Step 3 |
| 不回 raw object / unbounded metadata | Task 4 test `test_get_pod_events_tool_evidence_does_not_contain_raw_object` |
| Event list 數量限制 (max 10) | Task 2 `truncate_pod_events` |
| Message 長度截斷 (256 chars) | Task 2 `truncate_pod_events` |
| Message redaction (`Bearer`, `password=`) | Task 4 `test_get_pod_events_tool_redacts_bearer_token_in_message` |
| `get_pod_events` 在 registry 中註冊 | Task 5 CLI registration |
| Fake provider success path | Task 4 `test_get_pod_events_tool_returns_event_list_via_adapter` |
| Unauthorized cluster deny path | Task 4 `test_get_pod_events_tool_denies_cluster_outside_allowlist` |
| Unauthorized namespace deny path | Task 4 `test_get_pod_events_tool_denies_namespace_outside_allowlist` |
| Real adapter payload mapping | Task 3 `test_real_adapter_maps_pod_events_payload` |
| `get_pod_logs` 不做 | 無對應任何 task — 正確 |
