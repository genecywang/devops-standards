# OpenClaw Kubernetes Pod Events Design

## Objective

在既有 `openclaw_foundation/` Kubernetes tooling 上，新增第二個 read-only tool：`get_pod_events`，讓 investigation flow 在 `get_pod_status` 之外，能再往下一步查詢 pod 相關事件。

這一版的目標不是做完整 incident investigation，也不是加入 `logs`，而是延續目前已建立的 adapter / guardrail / error model 邊界，補上第二個可控的 Kubernetes read-only capability。

## Scope

這一版只包含：

- `KubernetesProviderAdapter` 新增 `get_pod_events(...)`
- `FakeKubernetesProviderAdapter` 與 `RealKubernetesProviderAdapter` 的 pod events 實作
- `get_pod_events` tool
- 對應測試

## Non-Goals

這一版不做：

- `get_pod_logs`
- multi-resource correlation
- cross-namespace search
- write action
- Slack integration
- multi-step planner

## Problem Statement

目前 `OpenClaw` 已有：

- `get_pod_status`
- fake / real provider
- domain error model
- CLI provider mode

但對 incident investigation 來說，只有 `pod status` 通常不夠。  
下一個最有價值且仍容易控制的查詢，通常是 `pod events`。

## Approaches

### 1. Tool-only Quick Add

直接加一個 `get_pod_events` tool，內部自己處理所有資料存取。

優點：

- 快

缺點：

- 破壞目前的 adapter boundary
- 之後其他 K8s tool 會開始重複邏輯

### 2. Adapter-first Extension

先擴充 `KubernetesProviderAdapter`，再新增 `get_pod_events` tool。

優點：

- 延續目前架構
- fake / real provider 行為清楚
- 後續 `get_pod_logs` / `describe_node` 也能沿用

缺點：

- 多一層改動

### 3. Events + Logs 一起做

一次補 `get_pod_events` 與 `get_pod_logs`。

優點：

- 功能感強

缺點：

- `logs` 的 truncation / redaction 難度高很多
- scope 容易失控

## Recommendation

採用 `Adapter-first Extension`。

原因：

- 目前 `OpenClaw` 的價值就在於受控 tool boundary
- `events` 很適合作為第二個 read-only tool
- 但不值得為了快而把 provider / tool / guardrail 邊界弄亂

## Core Design

### Adapter Contract

在 `KubernetesProviderAdapter` 新增：

- `get_pod_events(cluster: str, namespace: str, pod_name: str) -> list[dict[str, object]]`

設計原則：

- output 必須是 bounded、machine-friendly 的事件列表
- 不直接回整份 Kubernetes raw event object

### Fake Provider

`FakeKubernetesProviderAdapter.get_pod_events()` 先回固定事件列表，例如：

- `type`
- `reason`
- `message`
- `count`
- `last_timestamp`

其中 message 可以帶少量可 redaction 的字串，用來驗證 guardrail。

### Real Provider

`RealKubernetesProviderAdapter.get_pod_events()` 透過 Kubernetes events API，查詢同一個 pod 的事件，並轉成最小 bounded payload。

第一版最小欄位：

- `type`
- `reason`
- `message`
- `count`
- `last_timestamp`

保留原則：

- 不返回 unbounded metadata
- 不返回完整 object graph

### Tool Behavior

新增 `KubernetesPodEventsTool`：

- `tool_name = "get_pod_events"`
- 與 `get_pod_status` 一樣使用：
  - scope validation
  - truncation
  - redaction

`target` 至少需要：

- `cluster`
- `namespace`
- `pod_name`

### Output Shape

summary 應偏人可讀，但 evidence 必須結構化。

第一版方向：

- summary: `pod payments-api-123 has 2 recent events`
- evidence: `[{"type": "...", "reason": "...", ...}]`

### Truncation / Redaction

這一版不另建一套複雜 event-specific guard system，而是採最小策略：

- event list 數量要有限制
- message 過長要截斷
- message 內容仍走既有 redaction hook

這樣能控制輸出，不會像 `logs` 一樣快速失控。

## Testing

至少需要：

- fake adapter-backed success path
- unauthorized cluster / namespace deny path
- event evidence 不回 raw object
- event message 會經過 redaction
- real adapter payload mapping

## Acceptance Criteria

完成時應能：

- 在 registry 中註冊 `get_pod_events`
- 用 fake provider 跑完整 success path
- `events` 權限與 output contract 明確可控
- 不引入 `logs`

## Risks

- 若 event output 不做 bounded mapping，很快會回到 raw object 洩漏問題
- 若這一版同時做 `logs`，scope 會明顯膨脹
- 若 tool 不走 adapter，後面 Kubernetes tool 會開始各自長歪

## Implementation Handoff

下一步的 implementation plan 只需要處理：

- adapter contract extension
- fake / real pod events provider
- `get_pod_events` tool
- 對應測試

先不要做 `get_pod_logs`。
