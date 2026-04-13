# OpenClaw Kubernetes Error Model Design

## Objective

在既有 `openclaw_foundation/` 真實 Kubernetes provider 基礎上，建立一致的 Kubernetes domain error model，讓 `real provider` 的失敗路徑不再只回傳模糊的 `failed to read pod status`，而是能區分 config、endpoint、auth、resource 與 generic API failure。

這一版的目標不是新增第二個 tool，而是讓第一個真實 read-only tool 的錯誤語意可判讀、可顯示、可重用。

## Scope

這一版只包含：

- Kubernetes domain error hierarchy
- `get_pod_status` 真實 adapter 的 error mapping
- CLI 對 domain error 的簡短顯示與 next-step 提示
- 對應單元測試

## Non-Goals

這一版不做：

- 第二個 Kubernetes tool
- 獨立 diagnostics command
- 真實 cluster health probe
- 自動修復機制
- audit sink persistence
- 多 cluster routing

## Problem Statement

目前 `--provider real` 已經能走到真實 Kubernetes API path，但失敗時只有 generic `KubernetesApiError("failed to read pod status")`。

這會讓使用者無法快速區分：

- kubeconfig / service account 沒載到
- cluster endpoint 無法連線
- RBAC / auth 被拒絕
- pod 不存在
- 其他 API 異常

結果就是第一個真實 tool 雖然已經接起來，但 operability 不夠。

## Approaches

### 1. CLI-only Error Strings

只在 CLI catch 例外後印更友善字串。

優點：

- 實作快

缺點：

- 平台語意沒有被收斂
- 之後 API / Slack / agent 還要重做一次

### 2. Domain Error Model + CLI Mapping

先在 adapter 層做 domain error mapping，再由 CLI 顯示對應訊息。

優點：

- error semantics 可重用
- CLI 不需要知道底層 Kubernetes 例外細節
- 後續其他 tool 可以共用同一套分類

缺點：

- 多一點抽象

### 3. Full Diagnostics Framework

建立獨立 preflight / diagnose framework，主動檢查 config、DNS、RBAC、API health。

優點：

- 最完整

缺點：

- scope 過大
- 不適合目前階段

## Recommendation

採用 `Domain Error Model + CLI Mapping`。

原因：

- 這一版真正缺的是可判讀的錯誤語意，不是更多工具
- 後續不論 CLI、API、Slack、Hermes planner 都能共用同一套 error model
- 可以用最小成本改善 operability，而不擴成大型 diagnostics 系統

## Core Design

### Error Hierarchy

在 `adapters/kubernetes.py` 內建立：

- `KubernetesError`
- `KubernetesConfigError`
- `KubernetesEndpointUnreachableError`
- `KubernetesAccessDeniedError`
- `KubernetesResourceNotFoundError`
- `KubernetesApiError`

設計原則：

- `KubernetesError` 是所有 domain error 的共同父類
- `KubernetesApiError` 保留作為 generic fallback
- 子類別語意互斥，避免同一個錯誤同時代表 config 與 auth 問題

### Mapping Rules

#### Config Loading

`build_core_v1_api()` 維持：

- dependency 沒裝 -> `KubernetesConfigError`
- `in-cluster` 與 `kubeconfig` 都載入失敗 -> `KubernetesConfigError`

這一層不做 endpoint / auth 判斷，因為那是 config 載入後的 runtime 問題。

#### API Call

`RealKubernetesProviderAdapter.get_pod_status()` 內將底層例外映射成：

- DNS resolve failure / connect timeout / transport unreachable
  -> `KubernetesEndpointUnreachableError`
- HTTP 401 / 403
  -> `KubernetesAccessDeniedError`
- HTTP 404
  -> `KubernetesResourceNotFoundError`
- 其他 Kubernetes / transport 例外
  -> `KubernetesApiError`

這一版不追求完全覆蓋所有底層例外型別，但要先明確涵蓋最常見、最有操作意義的幾類。

### CLI Behavior

CLI 不再直接把 raw stack trace 丟給使用者。

當捕捉到 `KubernetesError` 時：

- 輸出簡短的錯誤摘要
- 額外輸出一行 `next check`
- 以 non-zero exit code 結束

範例方向：

- `kubernetes config unavailable`
  - `next check: verify in-cluster identity or kubeconfig context`
- `cluster endpoint unreachable`
  - `next check: verify DNS, network path, VPN, or cluster endpoint`
- `kubernetes access denied`
  - `next check: verify service account, IAM / RBAC permissions`
- `pod not found`
  - `next check: verify cluster, namespace, and pod_name`

CLI 不應輸出完整 Python traceback，除非未預期例外未被 domain error model 捕捉。

### Preflight Scope

這一版的 `preflight` 不是獨立探測流程，而是：

- config loading failure 在 provider build 階段就明確分類
- endpoint / auth / not found 在第一次 API call 時明確分類

也就是「分類清楚的失敗路徑」，不是額外做一套 probe command。

## Testing

至少需要：

- config loader failure -> `KubernetesConfigError`
- name resolution / transport failure -> `KubernetesEndpointUnreachableError`
- 403 -> `KubernetesAccessDeniedError`
- 404 -> `KubernetesResourceNotFoundError`
- generic runtime failure -> `KubernetesApiError`
- CLI 對每種 domain error 產生可理解訊息與 non-zero exit

不做：

- 依賴真實 cluster 的 integration test

## Acceptance Criteria

完成時應能：

- 讓 `get_pod_status` 的真實 adapter 失敗路徑回傳明確 domain error
- CLI 對常見錯誤給出簡短可操作的提示
- `fake provider` flow 不受影響
- 後續第二個 Kubernetes read-only tool 可重用同一套 error model

## Risks

- 若 error 類別切太細，現在會 over-engineer
- 若 CLI 直接綁底層 exception type，之後其他入口會重複實作
- 若把 preflight 做成完整 probe framework，這輪 scope 會被拉爆

## Implementation Handoff

下一步的 implementation plan 只需要處理：

- error hierarchy
- adapter error mapping
- CLI error rendering
- 對應測試

先不要做第二個 tool，也不要做獨立 diagnostics command。
