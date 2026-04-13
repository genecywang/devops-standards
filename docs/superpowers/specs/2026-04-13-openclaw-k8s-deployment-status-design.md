# OpenClaw Kubernetes Deployment Status Design

## Objective

在既有 `openclaw_foundation/` Kubernetes tooling 上，新增第三個 read-only tool：`get_deployment_status`，讓 `Self-Service Ops Copilot` 與未來 investigation flow 能快速查詢 deployment 的 rollout / availability 狀態。

這一版的目標不是做完整 rollout diagnosis，也不是把 deployment 背後的 pod、ReplicaSet、logs 一次展開，而是延續目前已建立的 adapter / guardrail / error model 邊界，補上一個 bounded、可控的 deployment-level 查詢能力。

## Scope

這一版只包含：

- `KubernetesProviderAdapter` 新增 `get_deployment_status(...)`
- `FakeKubernetesProviderAdapter` 與 `RealKubernetesProviderAdapter` 的 deployment status 實作
- `get_deployment_status` tool
- 對應測試

## Non-Goals

這一版不做：

- `get_recent_logs`
- `query_prometheus`
- 查 deployment 背後的 pod 清單
- 查 rollout history / ReplicaSet
- multi-step correlation
- write action
- Slack formatter rich output

## Problem Statement

目前 `OpenClaw` 已有：

- `get_pod_status`
- `get_pod_events`
- fake / real provider
- domain error model
- Slack `Self-Service Ops Copilot` MVP

但對日常 Read Ops 來說，deployment-level 狀態也是高頻需求。  
當使用者要回答的是「這個服務 rollout 是否健康」、「目前可用副本是否足夠」，直接查 deployment 通常比先查單一 pod 更合理。

下一個最有價值且仍容易控制的查詢，就是 `deployment status`。

## Approaches

### 1. Status-only Minimum

只回 deployment 的 replica counts：

- `desired_replicas`
- `ready_replicas`
- `available_replicas`
- `updated_replicas`

優點：

- 最簡單
- output 穩定

缺點：

- 對 rollout 問題的判讀資訊不足

### 2. Status + Rollout Conditions

除了 replica counts，也回 deployment conditions 的最小摘要：

- `type`
- `status`
- `reason`
- `message`

優點：

- 對 rollout / degraded 狀態更有判讀價值
- 仍可維持 bounded output

缺點：

- 比 status-only 稍微多一點 mapping 成本

### 3. Status + Pods Expansion

查 deployment 後，再展開關聯 pod 狀態。

優點：

- 資訊完整

缺點：

- 已經接近多步 investigation
- 會把這一輪 scope 拉大

## Recommendation

採用 `Status + Rollout Conditions`。

原因：

- deployment tool 的價值不只是 replica 數字，而是讓使用者知道 rollout 是否卡住或 degraded
- 只補最小 conditions 摘要，仍能維持固定 contract
- 不需要為了完整資訊而把 pod correlation 拉進同一個 tool

## Core Design

### Adapter Contract

在 `KubernetesProviderAdapter` 新增：

- `get_deployment_status(cluster: str, namespace: str, deployment_name: str) -> dict[str, object]`

設計原則：

- output 必須是 bounded、machine-friendly 的 deployment 摘要
- 不直接回整份 Kubernetes raw deployment object

### Fake Provider

`FakeKubernetesProviderAdapter.get_deployment_status()` 回固定 payload，例如：

- `deployment_name`
- `namespace`
- `desired_replicas`
- `ready_replicas`
- `available_replicas`
- `updated_replicas`
- `conditions`

其中 conditions 至少包含：

- `type`
- `status`
- `reason`
- `message`

### Real Provider

`RealKubernetesProviderAdapter.get_deployment_status()` 透過 AppsV1 API 查 deployment，並轉成最小 bounded payload。

第一版最小欄位：

- `deployment_name`
- `namespace`
- `desired_replicas`
- `ready_replicas`
- `available_replicas`
- `updated_replicas`
- `conditions`

保留原則：

- 不返回 annotation / labels 全量內容
- 不返回 raw object graph
- condition message 若過長，仍需經過既有 redaction / truncation 流程

### Tool Behavior

新增 `KubernetesDeploymentStatusTool`：

- `tool_name = "get_deployment_status"`
- 與既有 Kubernetes tools 一樣使用：
  - scope validation
  - truncation
  - redaction

`target` 至少需要：

- `cluster`
- `namespace`
- `resource_name`

這一版沿用 `resource_name`，對 deployment tool 即代表 deployment name。

### Output Shape

summary 應偏人可讀，但 evidence 必須結構化。

第一版方向：

- healthy summary:
  - `deployment payments-api is healthy: 3/3 ready, 3 available`
- progressing / degraded summary:
  - `deployment payments-api is degraded: 1/3 ready, 1 available`

evidence 方向：

```json
{
  "deployment_name": "payments-api",
  "namespace": "payments",
  "desired_replicas": 3,
  "ready_replicas": 1,
  "available_replicas": 1,
  "updated_replicas": 2,
  "conditions": [
    {
      "type": "Available",
      "status": "False",
      "reason": "MinimumReplicasUnavailable",
      "message": "Deployment does not have minimum availability."
    }
  ]
}
```

Slack formatter 這一輪仍只依賴 `summary`，不展開 evidence。

### Truncation / Redaction

這一版不另建 deployment-specific guard system，而是沿用最小策略：

- conditions 數量有限制
- condition message 過長要截斷
- message 內容仍走既有 redaction hook

## Testing

至少需要：

- fake adapter-backed success path
- unauthorized cluster / namespace deny path
- evidence 不回 raw object
- condition message 會經過 redaction
- real adapter payload mapping

## Acceptance Criteria

完成時應能：

- 在 registry 中註冊 `get_deployment_status`
- 用 fake provider 跑完整 success path
- CLI / Slack grammar 不需修改即可使用 `resource_name`
- deployment status 權限與 output contract 明確可控
- 不引入 pod expansion / logs

## Risks

- 若直接把 deployment raw object 往外回，bounded output 很快會失控
- 若同時加 rollout history / pod expansion，這一輪會從單一 tool 膨脹成 investigation bundle
- 若 summary 規則不固定，Slack reply 可讀性會變差

## Implementation Handoff

下一步的 implementation plan 只需要處理：

- adapter contract extension
- fake / real deployment provider
- `get_deployment_status` tool
- registry / CLI wiring
- 對應測試

先不要做：

- `get_recent_logs`
- `query_prometheus`
- deployment → pod correlation
