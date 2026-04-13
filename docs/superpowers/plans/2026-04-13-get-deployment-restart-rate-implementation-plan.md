# Get Deployment Restart Rate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `openclaw_foundation` 新增 `get_deployment_restart_rate`，以 Prometheus 3-way join 聚合 deployment 底下 pod 的 recent / total restart 訊號，並接進 `self_service_copilot`。

**Architecture:** 延伸 `PrometheusProviderAdapter` 新增 `get_deployment_restart_rate()`；`RealPrometheusProviderAdapter` 用四次 bounded query 做 Python orchestration；新增 `PrometheusDeploymentRestartRateTool` 組 summary 與 bounded pod breakdown；`self_service_copilot` 只補 registry 與 `supported_tools` 暴露。

**Tech Stack:** Python 3.11, Prometheus HTTP API, pytest, `openclaw_foundation`, `self_service_copilot`

---

## File Structure

| 狀態 | 路徑 | 責任 |
|------|------|------|
| 修改 | `openclaw_foundation/src/openclaw_foundation/adapters/prometheus.py` | adapter protocol、fake method、real 3-way join orchestration |
| 新增 | `openclaw_foundation/src/openclaw_foundation/tools/prometheus_deployment_restart_rate.py` | tool summary / evidence |
| 修改 | `openclaw_foundation/src/openclaw_foundation/cli.py` | registry wiring + fixture support |
| 新增 | `openclaw_foundation/fixtures/deployment_restart_rate_request.json` | CLI fixture |
| 新增 | `openclaw_foundation/tests/test_prometheus_deployment_restart_rate_tool.py` | tool-level tests |
| 修改 | `openclaw_foundation/tests/test_prometheus_adapter.py` | adapter orchestration tests |
| 修改 | `self_service_copilot/src/self_service_copilot/config.py` | expose `get_deployment_restart_rate` in supported tools |
| 修改 | `self_service_copilot/src/self_service_copilot/bot.py` | register new Prometheus tool |
| 修改 | `self_service_copilot/tests/test_config.py` | supported tools assertion |
| 修改 | `self_service_copilot/tests/test_bot.py` | registry assertion |

---

## Task 1: Extend Prometheus adapter contract and fake adapter

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/adapters/prometheus.py`
- Modify: `openclaw_foundation/tests/test_prometheus_adapter.py`

- [ ] **Step 1: Write failing fake-adapter contract test**

Append to `openclaw_foundation/tests/test_prometheus_adapter.py`:

```python
from openclaw_foundation.adapters.prometheus import FakePrometheusProviderAdapter


def test_fake_prometheus_adapter_returns_deployment_restart_rate_shape() -> None:
    adapter = FakePrometheusProviderAdapter()

    payload = adapter.get_deployment_restart_rate("payments", "payments-api")

    assert payload["namespace"] == "payments"
    assert payload["deployment_name"] == "payments-api"
    assert payload["recent_restarts_15m"] == 3
    assert payload["total_restarts"] == 7
    assert payload["pods_shown"] == 2
    assert payload["pods_total"] == 2
    assert payload["no_pods"] is False
    assert payload["window"] == "15m"
    assert len(payload["pod_breakdown"]) == 2
```

- [ ] **Step 2: Verify test fails**

Run:

```bash
cd openclaw_foundation
.venv/bin/python -m pytest tests/test_prometheus_adapter.py -k "deployment_restart_rate_shape" -q
```

Expected:

- `AttributeError` for missing `get_deployment_restart_rate`

- [ ] **Step 3: Implement protocol and fake method**

In `openclaw_foundation/src/openclaw_foundation/adapters/prometheus.py`:

1. Extend protocol:

```python
class PrometheusProviderAdapter(Protocol):
    def get_pod_runtime(self, namespace: str, pod_name: str) -> dict[str, object]: ...
    def get_deployment_restart_rate(
        self, namespace: str, deployment_name: str
    ) -> dict[str, object]: ...
```

2. Add fake method:

```python
    def get_deployment_restart_rate(
        self, namespace: str, deployment_name: str
    ) -> dict[str, object]:
        return {
            "namespace": namespace,
            "deployment_name": deployment_name,
            "recent_restarts_15m": 3,
            "total_restarts": 7,
            "pod_breakdown": [
                {
                    "pod_name": f"{deployment_name}-abc",
                    "recent_restarts_15m": 2,
                    "total_restarts": 4,
                },
                {
                    "pod_name": f"{deployment_name}-def",
                    "recent_restarts_15m": 1,
                    "total_restarts": 3,
                },
            ],
            "pods_shown": 2,
            "pods_total": 2,
            "no_pods": False,
            "window": "15m",
        }
```

- [ ] **Step 4: Verify fake-adapter test passes**

Run:

```bash
cd openclaw_foundation
.venv/bin/python -m pytest tests/test_prometheus_adapter.py -k "deployment_restart_rate_shape" -q
```

Expected:

- test passes

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/adapters/prometheus.py \
        openclaw_foundation/tests/test_prometheus_adapter.py
git commit -m "feat: add deployment restart contract to prometheus adapter"
```

---

## Task 2: Implement real adapter 3-way join orchestration

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/adapters/prometheus.py`
- Modify: `openclaw_foundation/tests/test_prometheus_adapter.py`

- [ ] **Step 1: Write failing orchestration tests**

Append to `openclaw_foundation/tests/test_prometheus_adapter.py`:

```python
from openclaw_foundation.adapters.prometheus import (
    PrometheusQueryError,
    RealPrometheusProviderAdapter,
)


def test_real_prometheus_adapter_builds_deployment_restart_payload(monkeypatch) -> None:
    adapter = RealPrometheusProviderAdapter(base_url="https://example.com")
    responses = [
        {
            "result": [
                {"metric": {"replicaset": "payments-api-rs1"}, "value": [0, "1"]},
                {"metric": {"replicaset": "payments-api-rs2"}, "value": [0, "1"]},
            ]
        },
        {
            "result": [
                {"metric": {"pod": "payments-api-pod-a"}, "value": [0, "1"]},
                {"metric": {"pod": "payments-api-pod-b"}, "value": [0, "1"]},
            ]
        },
        {
            "result": [
                {"metric": {"pod": "payments-api-pod-a"}, "value": [0, "4"]},
                {"metric": {"pod": "payments-api-pod-b"}, "value": [0, "3"]},
            ]
        },
        {
            "result": [
                {"metric": {"pod": "payments-api-pod-a"}, "value": [0, "2"]},
                {"metric": {"pod": "payments-api-pod-b"}, "value": [0, "1"]},
            ]
        },
    ]

    def fake_query(query: str):
        return responses.pop(0)

    monkeypatch.setattr(adapter, "query_instant", fake_query)

    payload = adapter.get_deployment_restart_rate("payments", "payments-api")

    assert payload["recent_restarts_15m"] == 3
    assert payload["total_restarts"] == 7
    assert payload["pods_shown"] == 2
    assert payload["pods_total"] == 2
    assert payload["no_pods"] is False
    assert payload["pod_breakdown"][0]["pod_name"] == "payments-api-pod-a"


def test_real_prometheus_adapter_raises_when_no_replicasets(monkeypatch) -> None:
    adapter = RealPrometheusProviderAdapter(base_url="https://example.com")
    monkeypatch.setattr(adapter, "query_instant", lambda query: {"result": []})

    try:
        adapter.get_deployment_restart_rate("payments", "payments-api")
        assert False, "expected PrometheusQueryError"
    except PrometheusQueryError as error:
        assert str(error) == "no replicasets found for deployment"


def test_real_prometheus_adapter_returns_no_pods_when_q2_is_empty(monkeypatch) -> None:
    adapter = RealPrometheusProviderAdapter(base_url="https://example.com")
    responses = [
        {"result": [{"metric": {"replicaset": "payments-api-rs1"}, "value": [0, "1"]}]},
        {"result": []},
    ]

    monkeypatch.setattr(adapter, "query_instant", lambda query: responses.pop(0))

    payload = adapter.get_deployment_restart_rate("payments", "payments-api")

    assert payload["recent_restarts_15m"] == 0
    assert payload["total_restarts"] == 0
    assert payload["pod_breakdown"] == []
    assert payload["no_pods"] is True


def test_real_prometheus_adapter_returns_missing_metrics_shape_when_q3_q4_are_empty(monkeypatch) -> None:
    adapter = RealPrometheusProviderAdapter(base_url="https://example.com")
    responses = [
        {"result": [{"metric": {"replicaset": "payments-api-rs1"}, "value": [0, "1"]}]},
        {"result": [{"metric": {"pod": "payments-api-pod-a"}, "value": [0, "1"]}]},
        {"result": []},
        {"result": []},
    ]

    monkeypatch.setattr(adapter, "query_instant", lambda query: responses.pop(0))

    payload = adapter.get_deployment_restart_rate("payments", "payments-api")

    assert payload["recent_restarts_15m"] == 0
    assert payload["total_restarts"] == 0
    assert payload["pod_breakdown"] == []
    assert payload["no_pods"] is False
```

- [ ] **Step 2: Verify tests fail**

Run:

```bash
cd openclaw_foundation
.venv/bin/python -m pytest tests/test_prometheus_adapter.py -k "deployment_restart" -q
```

Expected:

- failures because `RealPrometheusProviderAdapter.get_deployment_restart_rate` is missing

- [ ] **Step 3: Implement real adapter method**

In `openclaw_foundation/src/openclaw_foundation/adapters/prometheus.py`, add helpers and method:

```python
    def _result_series_names(self, result: list[dict[str, Any]], label: str) -> list[str]:
        names: list[str] = []
        for sample in result:
            metric = sample.get("metric", {})
            value = metric.get(label)
            if isinstance(value, str):
                names.append(value)
        return names

    def _regex_union(self, values: list[str]) -> str:
        escaped = [value.replace("-", "\\-") for value in values]
        return "|".join(escaped)

    def get_deployment_restart_rate(
        self, namespace: str, deployment_name: str
    ) -> dict[str, object]:
        rs_result = self.query_instant(
            f'kube_replicaset_owner{{owner_kind="Deployment",owner_name="{deployment_name}",namespace="{namespace}"}}'
        )["result"]
        if not rs_result:
            raise PrometheusQueryError("no replicasets found for deployment")

        replicasets = self._result_series_names(rs_result, "replicaset")
        rs_regex = self._regex_union(replicasets)

        pod_result = self.query_instant(
            f'kube_pod_owner{{owner_kind="ReplicaSet",owner_name=~"{rs_regex}",namespace="{namespace}"}}'
        )["result"]
        if not pod_result:
            return {
                "namespace": namespace,
                "deployment_name": deployment_name,
                "recent_restarts_15m": 0,
                "total_restarts": 0,
                "pod_breakdown": [],
                "pods_shown": 0,
                "pods_total": 0,
                "no_pods": True,
                "window": "15m",
            }

        pods = self._result_series_names(pod_result, "pod")
        pod_regex = self._regex_union(pods)

        total_result = self.query_instant(
            'sum by(pod)(kube_pod_container_status_restarts_total'
            f'{{pod=~"{pod_regex}",namespace="{namespace}"}})'
        )["result"]
        recent_result = self.query_instant(
            'sum by(pod)(increase(kube_pod_container_status_restarts_total'
            f'{{pod=~"{pod_regex}",namespace="{namespace}"}}[15m]))'
        )["result"]

        total_by_pod = {
            sample["metric"]["pod"]: int(float(sample["value"][1]))
            for sample in total_result
        }
        recent_by_pod = {
            sample["metric"]["pod"]: int(float(sample["value"][1]))
            for sample in recent_result
        }

        if not total_by_pod and not recent_by_pod:
            return {
                "namespace": namespace,
                "deployment_name": deployment_name,
                "recent_restarts_15m": 0,
                "total_restarts": 0,
                "pod_breakdown": [],
                "pods_shown": 0,
                "pods_total": len(pods),
                "no_pods": False,
                "window": "15m",
            }

        pod_breakdown = [
            {
                "pod_name": pod,
                "recent_restarts_15m": recent_by_pod.get(pod, 0),
                "total_restarts": total_by_pod.get(pod, 0),
            }
            for pod in pods
        ]
        pod_breakdown.sort(
            key=lambda item: (
                item["recent_restarts_15m"],
                item["total_restarts"],
            ),
            reverse=True,
        )
        pods_total = len(pod_breakdown)
        pod_breakdown = pod_breakdown[:5]

        return {
            "namespace": namespace,
            "deployment_name": deployment_name,
            "recent_restarts_15m": sum(recent_by_pod.values()),
            "total_restarts": sum(total_by_pod.values()),
            "pod_breakdown": pod_breakdown,
            "pods_shown": len(pod_breakdown),
            "pods_total": pods_total,
            "no_pods": False,
            "window": "15m",
        }
```

- [ ] **Step 4: Verify adapter tests pass**

Run:

```bash
cd openclaw_foundation
.venv/bin/python -m pytest tests/test_prometheus_adapter.py -k "deployment_restart" -q
```

Expected:

- all selected tests pass

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/adapters/prometheus.py \
        openclaw_foundation/tests/test_prometheus_adapter.py
git commit -m "feat: add deployment restart orchestration to prometheus adapter"
```

---

## Task 3: Add deployment restart rate tool

**Files:**
- Create: `openclaw_foundation/src/openclaw_foundation/tools/prometheus_deployment_restart_rate.py`
- Create: `openclaw_foundation/tests/test_prometheus_deployment_restart_rate_tool.py`

- [ ] **Step 1: Write failing tool tests**

Create `openclaw_foundation/tests/test_prometheus_deployment_restart_rate_tool.py`:

```python
from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest
from openclaw_foundation.tools.prometheus_deployment_restart_rate import (
    PrometheusDeploymentRestartRateTool,
)


class StubPrometheusAdapter:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def get_deployment_restart_rate(self, namespace: str, deployment_name: str) -> dict[str, object]:
        return self.payload


def build_request(namespace: str = "payments", resource_name: str = "payments-api") -> InvestigationRequest:
    return InvestigationRequest(
        request_type="investigation",
        request_id="req-1",
        source_product="test",
        input_ref="fixture://deployment-restart",
        budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=15,
            max_output_tokens=512,
        ),
        tool_name="get_deployment_restart_rate",
        scope={"cluster": "staging-main", "environment": "staging"},
        target={"namespace": namespace, "resource_name": resource_name},
    )


def test_tool_summary_uses_elevated_when_recent_restarts_exist() -> None:
    payload = {
        "namespace": "payments",
        "deployment_name": "payments-api",
        "recent_restarts_15m": 3,
        "total_restarts": 7,
        "pod_breakdown": [
            {"pod_name": "payments-api-a", "recent_restarts_15m": 2, "total_restarts": 4},
            {"pod_name": "payments-api-b", "recent_restarts_15m": 1, "total_restarts": 3},
        ],
        "pods_shown": 2,
        "pods_total": 2,
        "no_pods": False,
        "window": "15m",
    }
    tool = PrometheusDeploymentRestartRateTool(StubPrometheusAdapter(payload), {"payments"})

    result = tool.invoke(build_request())

    assert "restart activity is elevated" in result.summary
    assert "top pods: payments-api-a (2 recent, 4 total)" in result.summary


def test_tool_summary_uses_quiet_when_recent_restarts_are_zero() -> None:
    payload = {
        "namespace": "payments",
        "deployment_name": "payments-api",
        "recent_restarts_15m": 0,
        "total_restarts": 7,
        "pod_breakdown": [],
        "pods_shown": 0,
        "pods_total": 2,
        "no_pods": False,
        "window": "15m",
    }
    tool = PrometheusDeploymentRestartRateTool(StubPrometheusAdapter(payload), {"payments"})

    result = tool.invoke(build_request())

    assert "restart activity is quiet" in result.summary
    assert "no pod restart metrics found" in result.summary


def test_tool_summary_includes_truncation_note() -> None:
    payload = {
        "namespace": "payments",
        "deployment_name": "payments-api",
        "recent_restarts_15m": 5,
        "total_restarts": 9,
        "pod_breakdown": [
            {"pod_name": "payments-api-a", "recent_restarts_15m": 3, "total_restarts": 4},
            {"pod_name": "payments-api-b", "recent_restarts_15m": 2, "total_restarts": 3},
        ],
        "pods_shown": 2,
        "pods_total": 6,
        "no_pods": False,
        "window": "15m",
    }
    tool = PrometheusDeploymentRestartRateTool(StubPrometheusAdapter(payload), {"payments"})

    result = tool.invoke(build_request())

    assert "showing 2 of 6" in result.summary


def test_tool_summary_reports_no_pods_when_flag_is_true() -> None:
    payload = {
        "namespace": "payments",
        "deployment_name": "payments-api",
        "recent_restarts_15m": 0,
        "total_restarts": 0,
        "pod_breakdown": [],
        "pods_shown": 0,
        "pods_total": 0,
        "no_pods": True,
        "window": "15m",
    }
    tool = PrometheusDeploymentRestartRateTool(StubPrometheusAdapter(payload), {"payments"})

    result = tool.invoke(build_request())

    assert "no pods found for deployment" in result.summary


def test_tool_rejects_disallowed_namespace() -> None:
    payload = {
        "namespace": "payments",
        "deployment_name": "payments-api",
        "recent_restarts_15m": 0,
        "total_restarts": 0,
        "pod_breakdown": [],
        "pods_shown": 0,
        "pods_total": 0,
        "no_pods": True,
        "window": "15m",
    }
    tool = PrometheusDeploymentRestartRateTool(StubPrometheusAdapter(payload), {"payments"})

    try:
        tool.invoke(build_request(namespace="internal"))
        assert False, "expected PermissionError"
    except PermissionError:
        pass
```

- [ ] **Step 2: Verify tests fail**

Run:

```bash
cd openclaw_foundation
.venv/bin/python -m pytest tests/test_prometheus_deployment_restart_rate_tool.py -q
```

Expected:

- module import failure for missing tool file

- [ ] **Step 3: Implement tool**

Create `openclaw_foundation/src/openclaw_foundation/tools/prometheus_deployment_restart_rate.py`:

```python
from openclaw_foundation.adapters.prometheus import PrometheusProviderAdapter
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.models.responses import ToolResult


class PrometheusDeploymentRestartRateTool:
    tool_name = "get_deployment_restart_rate"
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
            raise ValueError("target is required for get_deployment_restart_rate")

        namespace = request.target["namespace"]
        deployment_name = request.target.get("resource_name")
        if deployment_name is None:
            raise ValueError("resource_name is required for get_deployment_restart_rate")
        if namespace not in self._allowed_namespaces:
            raise PermissionError("namespace is not allowed")

        payload = self._adapter.get_deployment_restart_rate(namespace, deployment_name)
        state = "quiet" if payload["recent_restarts_15m"] == 0 else "elevated"
        summary = (
            f"deployment {deployment_name} restart activity is {state}: "
            f"{payload['recent_restarts_15m']} restarts in {payload['window']}, "
            f"{payload['total_restarts']} total"
        )

        pod_breakdown = payload["pod_breakdown"]
        if pod_breakdown:
            top_pods = ", ".join(
                f"{item['pod_name']} ({item['recent_restarts_15m']} recent, {item['total_restarts']} total)"
                for item in pod_breakdown
            )
            if payload["pods_shown"] < payload["pods_total"]:
                summary += (
                    f" top pods: {top_pods}, ... "
                    f"(showing {payload['pods_shown']} of {payload['pods_total']})"
                )
            else:
                summary += f" top pods: {top_pods}"
        elif payload["no_pods"]:
            summary += " no pods found for deployment"
        else:
            summary += " no pod restart metrics found"

        return ToolResult(summary=summary, evidence=[payload])
```

- [ ] **Step 4: Verify tool tests pass**

Run:

```bash
cd openclaw_foundation
.venv/bin/python -m pytest tests/test_prometheus_deployment_restart_rate_tool.py -q
```

Expected:

- all tests pass

- [ ] **Step 5: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/tools/prometheus_deployment_restart_rate.py \
        openclaw_foundation/tests/test_prometheus_deployment_restart_rate_tool.py
git commit -m "feat: add deployment restart rate tool"
```

---

## Task 4: Wire CLI and fixture

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/cli.py`
- Create: `openclaw_foundation/fixtures/deployment_restart_rate_request.json`

- [ ] **Step 1: Add failing CLI coverage via existing registry expectations**

Append to the registry-building section in `openclaw_foundation/src/openclaw_foundation/cli.py` by planning to register the new tool. No dedicated test file is required in this task; verification will be via CLI smoke command.

- [ ] **Step 2: Register the new tool in CLI**

In `openclaw_foundation/src/openclaw_foundation/cli.py`:

1. Add import:

```python
from openclaw_foundation.tools.prometheus_deployment_restart_rate import (
    PrometheusDeploymentRestartRateTool,
)
```

2. In registry creation, register:

```python
    registry.register(
        PrometheusDeploymentRestartRateTool(
            adapter=prometheus_adapter,
            allowed_namespaces={request.target["namespace"]},
        )
    )
```

3. Create `openclaw_foundation/fixtures/deployment_restart_rate_request.json`:

```json
{
  "request_type": "investigation",
  "request_id": "req-deployment-restart-001",
  "source_product": "cli_fixture",
  "input_ref": "fixture://deployment_restart_rate",
  "scope": {
    "cluster": "staging-main",
    "environment": "staging"
  },
  "budget": {
    "max_steps": 2,
    "max_tool_calls": 1,
    "max_duration_seconds": 15,
    "max_output_tokens": 512
  },
  "tool_name": "get_deployment_restart_rate",
  "target": {
    "namespace": "payments",
    "resource_name": "payments-api"
  }
}
```

- [ ] **Step 3: Verify CLI smoke path**

Run:

```bash
PYTHONPATH=openclaw_foundation/src \
openclaw_foundation/.venv/bin/python -m openclaw_foundation.cli \
  --fixture openclaw_foundation/fixtures/deployment_restart_rate_request.json
```

Expected:

- output contains `deployment payments-api restart activity is elevated`

- [ ] **Step 4: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/cli.py \
        openclaw_foundation/fixtures/deployment_restart_rate_request.json
git commit -m "feat: wire deployment restart rate into cli"
```

---

## Task 5: Wire Self-Service Copilot exposure

**Files:**
- Modify: `self_service_copilot/src/self_service_copilot/config.py`
- Modify: `self_service_copilot/src/self_service_copilot/bot.py`
- Modify: `self_service_copilot/tests/test_config.py`
- Modify: `self_service_copilot/tests/test_bot.py`

- [ ] **Step 1: Write failing copilot tests**

Append to `self_service_copilot/tests/test_config.py`:

```python
def test_from_env_includes_get_deployment_restart_rate_in_supported_tools(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_CLUSTER", "staging-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "staging")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "staging-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "payments")
    monkeypatch.setenv("COPILOT_PROVIDER", "fake")
    monkeypatch.delenv("COPILOT_ALLOWED_CHANNEL_IDS", raising=False)

    config = CopilotConfig.from_env()

    assert "get_deployment_restart_rate" in config.supported_tools
```

Append to `self_service_copilot/tests/test_bot.py`:

```python
def test_build_registry_registers_get_deployment_restart_rate_tool() -> None:
    config = CopilotConfig(
        cluster="staging-main",
        environment="staging",
        allowed_clusters={"staging-main"},
        allowed_namespaces={"payments"},
        prometheus_base_url=None,
        supported_tools=frozenset(
            {
                "get_pod_status",
                "get_pod_events",
                "get_deployment_status",
                "get_pod_runtime",
                "get_deployment_restart_rate",
            }
        ),
        default_budget=ExecutionBudget(
            max_steps=2,
            max_tool_calls=1,
            max_duration_seconds=15,
            max_output_tokens=512,
        ),
        provider="fake",
        allowed_channel_ids=set(),
        user_rate_limit_count=5,
        user_rate_limit_window_seconds=60,
        channel_rate_limit_count=20,
        channel_rate_limit_window_seconds=60,
    )

    registry = build_registry(config)

    tool = registry.get("get_deployment_restart_rate")
    assert tool.tool_name == "get_deployment_restart_rate"
```

- [ ] **Step 2: Verify tests fail**

Run:

```bash
cd self_service_copilot
.venv/bin/python -m pytest tests/test_config.py -k "deployment_restart_rate" -q
.venv/bin/python -m pytest tests/test_bot.py -k "deployment_restart_rate" -q
```

Expected:

- supported_tools test fails
- registry lookup test fails

- [ ] **Step 3: Implement config and registry wiring**

1. In `self_service_copilot/src/self_service_copilot/config.py`, add to `supported_tools`:

```python
                    "get_deployment_restart_rate",
```

2. In `self_service_copilot/src/self_service_copilot/bot.py`, add import:

```python
from openclaw_foundation.tools.prometheus_deployment_restart_rate import (
    PrometheusDeploymentRestartRateTool,
)
```

3. Register tool in `build_registry()`:

```python
    registry.register(
        PrometheusDeploymentRestartRateTool(
            adapter=prometheus_adapter,
            allowed_namespaces=config.allowed_namespaces,
        )
    )
```

- [ ] **Step 4: Verify copilot tests pass**

Run:

```bash
cd self_service_copilot
.venv/bin/python -m pytest tests/test_config.py -q
.venv/bin/python -m pytest tests/test_bot.py -q
```

Expected:

- all tests pass

- [ ] **Step 5: Commit**

```bash
git add self_service_copilot/src/self_service_copilot/config.py \
        self_service_copilot/src/self_service_copilot/bot.py \
        self_service_copilot/tests/test_config.py \
        self_service_copilot/tests/test_bot.py
git commit -m "feat: expose deployment restart rate to copilot"
```

---

## Task 6: Full verification

**Files:**
- Modify: any files from Tasks 1-5 if fixes are needed

- [ ] **Step 1: Run targeted foundation tests**

Run:

```bash
cd openclaw_foundation
.venv/bin/python -m pytest \
  tests/test_prometheus_adapter.py \
  tests/test_prometheus_deployment_restart_rate_tool.py -q
```

Expected:

- all targeted tests pass

- [ ] **Step 2: Run full foundation suite**

Run:

```bash
openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests -q
```

Expected:

- full suite passes

- [ ] **Step 3: Run full copilot suite**

Run:

```bash
cd self_service_copilot
.venv/bin/python -m pytest tests -q
```

Expected:

- full suite passes

- [ ] **Step 4: Optional manual smoke**

If desired, run:

```bash
PYTHONPATH=openclaw_foundation/src \
openclaw_foundation/.venv/bin/python -m openclaw_foundation.cli \
  --fixture openclaw_foundation/fixtures/deployment_restart_rate_request.json
```

Expected:

- summary string for deployment restart activity

- [ ] **Step 5: Final commit**

```bash
git status --short
```

Confirm no unintended files are staged, then:

```bash
git add openclaw_foundation/src/openclaw_foundation/adapters/prometheus.py \
        openclaw_foundation/src/openclaw_foundation/tools/prometheus_deployment_restart_rate.py \
        openclaw_foundation/src/openclaw_foundation/cli.py \
        openclaw_foundation/fixtures/deployment_restart_rate_request.json \
        openclaw_foundation/tests/test_prometheus_adapter.py \
        openclaw_foundation/tests/test_prometheus_deployment_restart_rate_tool.py \
        self_service_copilot/src/self_service_copilot/config.py \
        self_service_copilot/src/self_service_copilot/bot.py \
        self_service_copilot/tests/test_config.py \
        self_service_copilot/tests/test_bot.py
git commit -m "feat: add deployment restart rate tool"
```
