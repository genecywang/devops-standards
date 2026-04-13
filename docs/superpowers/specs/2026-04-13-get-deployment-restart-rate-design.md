# Get Deployment Restart Rate Design

**Date:** 2026-04-13
**Scope:** `get_deployment_restart_rate` tool in `openclaw_foundation`
**Status:** Proposed

## Context

`openclaw_foundation` 已有：

- `get_pod_status` — pod 級別狀態
- `get_pod_events` — pod 事件
- `get_deployment_status` — deployment rollout 狀態
- `get_pod_runtime` — 單 pod Prometheus runtime 訊號

缺少的是：以 deployment 為單位，聚合底下所有 pod 的 restart activity。
`get_deployment_restart_rate` 填補這個缺口，讓 operator 能快速判斷「這個 deployment 現在有沒有在抖」。

---

## Goals

- 以 `deployment_name` + `namespace` 為輸入，查 Prometheus 回答：
  - 最近 15 分鐘有沒有 restart（主訊號）
  - cumulative total restart（背景參考）
  - 哪幾個 pod 最值得看（bounded per-pod 明細）
- 不改 Kubernetes API call 路徑（純 Prometheus）
- 放在 `openclaw_foundation/`，不依賴 `self_service_copilot/`

## Non-Goals

- per-container 明細
- restart 歷史趨勢（多個時間點）
- alert threshold 判斷
- 修改 RBAC（Prometheus 走 HTTP，非 K8s API）

---

## 1. Implementation Approach

### 路線：Prometheus 3-way join（Python orchestration）

Prometheus 不支援跨 metric 的 SQL-style join，因此用 Python 分四次 query 後聚合：

**Query 1：** 取得 deployment 底下的 ReplicaSet 名單
```promql
kube_replicaset_owner{owner_kind="Deployment", owner_name="<deployment>", namespace="<namespace>"}
```

**Query 2：** 取得那些 ReplicaSet 底下的 pod 名單
```promql
kube_pod_owner{owner_kind="ReplicaSet", owner_name=~"rs1|rs2|...", namespace="<namespace>"}
```

**Query 3：** 取得 pod 的 cumulative restart count（per pod，所有 container 加總）
```promql
sum by(pod)(kube_pod_container_status_restarts_total{pod=~"pod1|pod2|...", namespace="<namespace>"})
```

**Query 4：** 取得最近 15 分鐘的 restart increase（per pod）
```promql
sum by(pod)(increase(kube_pod_container_status_restarts_total{pod=~"...", namespace="<namespace>"}[15m]))
```

Python 負責：
- 從 Q1 結果萃取 replicaset 名稱
- 從 Q2 結果萃取 pod 名稱
- 將 Q3 / Q4 結果 merge 成 per-pod dict
- 聚合 total 與 recent
- 排序 + truncate（max 5 pods）

---

## 2. Output Shape

Adapter method 回傳 `dict[str, object]`（與現有 `get_pod_runtime` 一致）：

```python
{
    "namespace": "payments",
    "deployment_name": "payments-api",
    "recent_restarts_15m": 3,
    "total_restarts": 7,
    "pod_breakdown": [
        {"pod_name": "payments-api-abc", "recent_restarts_15m": 2, "total_restarts": 4},
        {"pod_name": "payments-api-def", "recent_restarts_15m": 1, "total_restarts": 3},
    ],
    "pods_shown": 2,
    "pods_total": 2,
    "no_pods": False,
    "window": "15m",
}
```

`pod_breakdown` 排序規則：`recent_restarts_15m` desc，相同時 `total_restarts` desc，最多 5 筆。

`pods_shown` / `pods_total` 讓 tool layer 能判斷是否有 truncation。

---

## 3. Tool Summary

Tool 的 `summary` 語意：

| 條件 | 語意詞 | 範例 |
|------|--------|------|
| `recent_restarts_15m == 0` | `quiet` | `deployment payments-api restart activity is quiet: 0 restarts in 15m, 7 total` |
| `recent_restarts_15m > 0` | `elevated` | `deployment payments-api restart activity is elevated: 3 restarts in 15m, 7 total` |

有 truncation 時（`pods_shown < pods_total`），summary 附加：
```
  top pods: payments-api-abc (2 recent, 4 total), ... (showing 5 of 12)
```

無 truncation 時附加：
```
  top pods: payments-api-abc (2 recent, 4 total), payments-api-def (1 recent, 3 total)
```

若 `pod_breakdown` 為空，分兩種情況：

- Q2 無結果（沒有 pod ownership）→ summary 附加：
  ```
    no pods found for deployment
  ```
- Q2 有結果但 Q3/Q4 都無結果（pod 存在但 metrics 缺失）→ summary 附加：
  ```
    no pod restart metrics found
  ```

---

## 4. File Structure

新增：
```
openclaw_foundation/src/openclaw_foundation/tools/prometheus_deployment_restart_rate.py
openclaw_foundation/tests/test_prometheus_deployment_restart_rate_tool.py
```

修改：
```
openclaw_foundation/src/openclaw_foundation/adapters/prometheus.py
    - PrometheusProviderAdapter Protocol 新增 get_deployment_restart_rate()
    - FakePrometheusProviderAdapter 新增固定 shape method
    - RealPrometheusProviderAdapter 新增 4-query orchestration method

openclaw_foundation/tests/test_prometheus_adapter.py  (或現有 test 檔)
    - FakeAdapter 回傳結構測試
    - RealAdapter query orchestration 測試（mock query_instant）

self_service_copilot/src/self_service_copilot/bot.py
    - build_registry() 新增 PrometheusDeploymentRestartRateTool registration

self_service_copilot/src/self_service_copilot/config.py
    - supported_tools default 新增 "get_deployment_restart_rate"

self_service_copilot/tests/test_bot.py
    - 新增 build_registry 包含 get_deployment_restart_rate 的 assertion

self_service_copilot/tests/test_config.py
    - 新增 supported_tools 包含 get_deployment_restart_rate 的 assertion
```

---

## 5. Adapter API

### Protocol 新增

```python
class PrometheusProviderAdapter(Protocol):
    def get_pod_runtime(self, namespace: str, pod_name: str) -> dict[str, object]: ...
    def get_deployment_restart_rate(self, namespace: str, deployment_name: str) -> dict[str, object]: ...
```

### FakePrometheusProviderAdapter

固定回傳 bounded shape，不模擬 Prometheus 中間 query 狀態：

```python
def get_deployment_restart_rate(self, namespace: str, deployment_name: str) -> dict[str, object]:
    return {
        "namespace": namespace,
        "deployment_name": deployment_name,
        "recent_restarts_15m": 3,
        "total_restarts": 7,
        "pod_breakdown": [
            {"pod_name": f"{deployment_name}-abc", "recent_restarts_15m": 2, "total_restarts": 4},
            {"pod_name": f"{deployment_name}-def", "recent_restarts_15m": 1, "total_restarts": 3},
        ],
        "pods_shown": 2,
        "pods_total": 2,
        "no_pods": False,
        "window": "15m",
    }
```

### RealPrometheusProviderAdapter

4-step orchestration（詳細 PromQL 見 Section 1）。

Edge cases：
- Q1 無結果（deployment 不存在或無 RS）→ `PrometheusQueryError("no replicasets found for deployment")`
- Q2 無結果（RS 存在但無 pod ownership）→ 回傳 `recent_restarts_15m=0, total_restarts=0, pod_breakdown=[], no_pods=True`
- Q2 有結果但 Q3/Q4 都無結果（pod 存在但 metrics 缺失）→ 回傳 `recent_restarts_15m=0, total_restarts=0, pod_breakdown=[], no_pods=False`
- pod 在 Q3 有值但 Q4 無值（increase 查不到）→ 視為 `recent_restarts_15m=0`

Tool layer 透過 `no_pods` 欄位區分兩種空結果，產生不同 summary 文字。

---

## 6. Tool Class

```python
class PrometheusDeploymentRestartRateTool:
    tool_name = "get_deployment_restart_rate"
    supported_request_types = ("investigation",)

    def __init__(
        self,
        adapter: PrometheusProviderAdapter,
        allowed_namespaces: set[str],
    ) -> None: ...

    def invoke(self, request: InvestigationRequest) -> ToolResult: ...
```

`invoke()` 從 `request.target` 取 `namespace` + `resource_name`（作為 `deployment_name`），namespace allowlist check 與其他 tool 一致。

---

## 7. Testing

### `test_prometheus_adapter.py`

- `FakePrometheusProviderAdapter.get_deployment_restart_rate()` 回傳正確 shape
- `RealPrometheusProviderAdapter.get_deployment_restart_rate()` with mocked `query_instant`：
  - 正常 3-way join 產出正確聚合值
  - Q1 無結果 → raise `PrometheusQueryError`
  - Q2 無結果 → 回傳 `no_pods=True, pod_breakdown=[]`
  - Q2 有結果但 Q3/Q4 空 → 回傳 `no_pods=False, pod_breakdown=[]`
  - Q4 無結果 → recent 視為 0

### `test_prometheus_deployment_restart_rate_tool.py`

- `recent_restarts_15m > 0` → summary 含 `elevated`
- `recent_restarts_15m == 0` → summary 含 `quiet`
- `pods_shown < pods_total` → summary 含 `showing N of M`
- `no_pods=True` → summary 含 `no pods found for deployment`
- `no_pods=False, pod_breakdown=[]` → summary 含 `no pod restart metrics found`
- namespace 不在 allowed list → raise `PermissionError`

### `test_bot.py`

- `build_registry()` 包含 `get_deployment_restart_rate` tool

---

## 8. Trade-offs

### Multi-query vs 單一 PromQL

PromQL 不支援 3-way metric join（不同 metric 的 label 名稱不相同，無法用 `on()` 連接），必須用 Python orchestration。代價是 4 次 HTTP round-trip，但 Prometheus 查詢延遲通常 < 100ms，累計 < 400ms，對 Slack bot 可接受。

### Fake adapter 固定 shape

Fake 不模擬 Prometheus 行為，只回傳固定 dict。好處是 tool tests / formatter tests 不依賴 Prometheus 實作細節，職責分離更清楚。Real adapter 的 orchestration logic 由 `test_prometheus_adapter.py` 單獨覆蓋（mock `query_instant`）。

### Pod breakdown 上限 5

Slack message 長度有限制，bounded 避免爆版。5 個在排障場景已足夠定位問題 pod。
