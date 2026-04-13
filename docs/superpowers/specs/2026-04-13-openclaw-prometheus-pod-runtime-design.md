# OpenClaw Prometheus Pod Runtime Design

## Objective

在既有 `openclaw_foundation/` read-only tooling 上，新增第一個 Prometheus-backed preset：`pod_runtime`，讓 `Self-Service Ops Copilot` 能查詢 workload 最近的 runtime 穩定性訊號，而不開放任意 PromQL。

這一版的目標不是做通用 metrics query console，也不是一次補齊 CPU / memory / latency，而是先把最穩定、最容易 bounded 的 runtime 指標固化成受控 capability。

## Scope

這一版只包含：

- 一個新的 Prometheus adapter 邊界
- 一個新的 read-only tool / preset：`get_pod_runtime`
- Slack / CLI 可消費的 bounded summary
- 對應測試

## Non-Goals

這一版不做：

- raw PromQL 輸入
- `query_prometheus` 通用查詢介面
- `service_traffic`
- CPU / memory 資源摘要
- logs / events correlation
- Grafana deep link

## Problem Statement

目前 `OpenClaw` 已有：

- `get_pod_status`
- `get_pod_events`
- `get_deployment_status`
- `Self-Service Ops Copilot` Slack MVP

但這些工具大多回答「現在長什麼樣」，還缺少「最近穩不穩」這個時間維度。

從實際 Prometheus discovery 可確認：

- `kube_pod_status_ready`
- `kube_pod_container_status_restarts_total`

在目標環境可查，且能透過 `namespace + pod` label 穩定定位特定 pod。

因此第一個最合理的 Prometheus preset 是 `pod_runtime`。

## Approaches

### 1. Generic PromQL Input

讓使用者直接傳 PromQL。

優點：

- 最自由

缺點：

- 邊界、治理、成本、formatter 都會失控

### 2. Preset Runtime Summary

固定查少量 runtime 指標：

- pod readiness
- restart count / restart increase

優點：

- input 可控
- output 可控
- 最適合 Slack

缺點：

- 彈性較低

### 3. Full Runtime Bundle

一次包含 runtime、resource、events、logs 摘要。

優點：

- 資訊完整

缺點：

- 這一輪 scope 明顯過大

## Recommendation

採用 `Preset Runtime Summary`。

原因：

- 這是第一個 Prometheus-backed capability，應該先證明 adapter / query / bounded output 路徑
- `ready` / `restart` 是最穩的 workload runtime 訊號
- 對 Copilot 來說，已足夠回答「最近穩不穩」

## Core Design

### Product Surface

第一版不直接暴露 raw PromQL，也不叫使用者輸入 query key。

建議 tool 名稱：

- `get_pod_runtime`

Slack grammar：

```text
@copilot get_pod_runtime <namespace> <resource_name>
```

其中 `resource_name` 代表 pod name。

### Adapter Boundary

新增一個 Prometheus adapter，例如：

- `PrometheusProviderAdapter`

第一版只需要一個方法：

- `get_pod_runtime(namespace: str, pod_name: str) -> dict[str, object]`

回傳 payload 方向：

- `namespace`
- `pod_name`
- `ready`
- `restart_count`
- `recent_restart_increase`

### Query Strategy

第一版只查兩類 metrics：

1. readiness

```promql
kube_pod_status_ready{namespace="<ns>", pod="<pod>", condition="true"}
```

2. restart count

```promql
kube_pod_container_status_restarts_total{namespace="<ns>", pod="<pod>"}
```

3. recent restart increase（固定 window，例如 15m）

```promql
sum(increase(kube_pod_container_status_restarts_total{namespace="<ns>", pod="<pod>"}[15m]))
```

設計原則：

- 不接受使用者自訂 window
- 第一版固定 `15m`
- 查詢結果必須彙整成單一 bounded payload

### Aggregation Rules

因為 restart metric 可能依 container 拆開，所以需要在 adapter 內統一聚合：

- `restart_count` = 所有 container restart count 總和
- `recent_restart_increase` = 所有 container 最近 15m increase 總和
- `ready` = `kube_pod_status_ready == 1`

### Tool Behavior

新增 tool：

- `tool_name = "get_pod_runtime"`

`target` 至少需要：

- `namespace`
- `resource_name`

summary 方向：

- stable：
  - `pod dev-py3-h2s-apisvc-5596c5b6bb-7hrg7 runtime looks stable: ready, 0 restarts in 15m`
- unstable：
  - `pod dev-py3-h2s-apisvc-5596c5b6bb-7hrg7 runtime is unstable: not ready, 3 restarts in 15m`

evidence 方向：

```json
{
  "namespace": "dev",
  "pod_name": "dev-py3-h2s-apisvc-5596c5b6bb-7hrg7",
  "ready": true,
  "restart_count": 0,
  "recent_restart_increase": 0.0,
  "window": "15m"
}
```

Slack formatter 這一輪仍只依賴 `summary`。

## Testing

至少需要：

- fake Prometheus adapter success path
- bounded payload mapping
- ready / restart summary formatting
- namespace allowlist deny path
- fixed 15m window aggregation

## Acceptance Criteria

完成時應能：

- CLI / Slack 呼叫 `get_pod_runtime`
- 回固定 bounded summary
- 不暴露 raw PromQL
- 固定使用 `15m` restart increase window
- 不需要修改現有 Slack grammar 結構

## Risks

- 若直接走 raw PromQL，這一輪很快變成 query console
- 若把 CPU / memory 一起塞進來，會和 `pod_resource` 混成一團
- 若不做 container-level aggregation，restart count 容易讓使用者看不懂

## Implementation Handoff

下一步 implementation plan 只需要處理：

- Prometheus adapter skeleton
- fake / real pod runtime query
- `get_pod_runtime` tool
- CLI wiring
- `Self-Service Ops Copilot` registry / supported tools

先不要做：

- `pod_resource`
- `service_traffic`
- generic `query_prometheus`
