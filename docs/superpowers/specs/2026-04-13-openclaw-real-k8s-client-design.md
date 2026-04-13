# OpenClaw Real Kubernetes Client Design

## Objective

在既有 `openclaw_foundation/` Kubernetes tooling 基礎上，替 `get_pod_status` 接入真實 Kubernetes client，同時維持目前已建立的 adapter boundary、guardrail flow 與可測試性。

這一版的目標不是擴充新的 tool，而是讓既有的 `get_pod_status` 可以在兩種環境都工作：

- `in-cluster`
- `local` 透過 `kubeconfig`

## Scope

這一版只包含：

- 真實 Kubernetes client factory
- `in-cluster -> kubeconfig` 的載入順序
- 真實 provider adapter implementation
- CLI 的 provider mode 選擇
- 對應單元測試

## Non-Goals

這一版不做：

- 新的 Kubernetes tool
- write action
- cluster context discovery / auto-switching
- kubeconfig path 的複雜覆寫策略
- 真實 cluster integration test
- audit sink persistence

## Proposed Layout

新增或擴充：

```text
openclaw_foundation/
  src/openclaw_foundation/
    adapters/
      kubernetes.py
    cli.py
  tests/
    test_kubernetes_adapter.py
    test_cli.py
```

## Approaches

### 1. Adapter 內建雙模式載入

由 `RealKubernetesProviderAdapter` 直接在建構時處理 config 載入。

優點：

- 呼叫點少
- 看起來直觀

缺點：

- config loading 與 provider call 責任混在一起
- 測試時不容易替換 client 建立流程

### 2. Client Factory + Thin Adapter

把 config 載入放在 `adapters/kubernetes.py` 的 factory，adapter 只負責呼叫 CoreV1 API 並整理輸出。

優點：

- 邊界清楚
- adapter 測試容易做 mock
- 後續新增 K8s tool 可重用同一個 client factory

缺點：

- 多一層抽象

### 3. CLI 決定載入模式

CLI 自己建立 Kubernetes client，再傳進 adapter。

優點：

- 實作快

缺點：

- library boundary 被 CLI 汙染
- 之後非 CLI 呼叫者很難共用同一套邏輯

## Recommendation

採用 `Client Factory + Thin Adapter`。

原因：

- 這和目前的 provider adapter 方向一致
- 後續接 `get_pod_events` 或 `get_pod_logs` 時，不需要重做 config loading
- CLI 只負責組裝，不負責實際的 Kubernetes config semantics

## Core Design

### Client Loading Order

固定採用：

1. 先嘗試 `load_incluster_config()`
2. 若失敗，再嘗試 `load_kube_config()`
3. 兩者都失敗時，丟出明確錯誤，讓 CLI 與呼叫端知道目前沒有可用的 Kubernetes config

這個順序的理由是：

- 在 pod 內執行時，應優先使用 service account identity
- 在本機開發時，自然 fallback 到 `kubeconfig`

### Adapter Boundary

`KubernetesProviderAdapter` protocol 不變，仍維持：

- `get_pod_status(cluster: str, namespace: str, pod_name: str) -> dict[str, object]`

新增一個真實實作：

- `RealKubernetesProviderAdapter`

它只負責：

- 使用已建立的 CoreV1 API client
- 呼叫 `read_namespaced_pod_status`
- 轉成目前 tool layer 可接受的 bounded payload

它不負責：

- scope validation
- truncation
- redaction
- audit

這些責任維持在既有 tool / runtime guardrail。

### Cluster Handling

第一版不做多 cluster routing，也不在 runtime 內動態切 context。

處理方式固定為：

- `cluster` 繼續保留在 request target 與 audit event 中，用於 scope 與稽核語意
- 真實 adapter 只使用目前載入到的單一 Kubernetes config

這代表：

- `cluster` 在這一版是 policy label，不是實際切換 context 的控制面
- 若本機或 pod 連到的 cluster 與 request 宣告的 `cluster` 不一致，這是呼叫端配置問題，不在這一版處理

這個限制是刻意的，因為現在先要驗證真 client path，不是解多 cluster orchestration。

### CLI Behavior

CLI 新增明確模式切換，例如：

- `--provider fake`
- `--provider real`

預設維持 `fake`。

理由：

- 測試與本機 smoke run 不能強依賴真 cluster
- 使用者要走真 client 時，必須明確表達意圖

當 `--provider real` 時：

- CLI 透過 client factory 建立真實 Kubernetes API client
- 若 config 載入失敗，CLI 應直接失敗並顯示可理解的錯誤

## Error Handling

至少要明確區分：

- 無可用 Kubernetes config
- API 呼叫失敗
- pod 不存在

錯誤原則：

- 不吞例外
- 轉成可理解的 domain error 訊息
- 不在錯誤字串中洩漏 credential 或敏感 config 內容

## Testing

至少需要：

- client factory 在 `in-cluster` 成功時不會再 fallback `kubeconfig`
- `in-cluster` 失敗時會 fallback `kubeconfig`
- 兩種 config 都失敗時會回明確錯誤
- 真實 adapter 會把 Kubernetes response 轉成既有 bounded payload
- CLI 在 `--provider fake` 與 `--provider real` 下走不同組裝路徑

不做：

- 依賴真實 cluster 的 integration test

## Acceptance Criteria

完成時應能：

- 保留既有 fake provider path，不破壞目前測試
- 在 `--provider real` 下建立真實 Kubernetes API client
- 同時支援 `in-cluster` 與 `local kubeconfig`
- 不把 config loading responsibility 混進 tool 本體
- 後續新增第二個 Kubernetes read-only tool 時，可直接重用同一個 client factory

## Risks

- 若把 `cluster` 當成真實 context switch 來源，這一版 scope 會快速膨脹到多 cluster routing
- 若把真實 client 初始化放進 CLI 之外但又不抽 factory，adapter 測試會變脆弱
- 若讓 `real` 成為 CLI 預設，開發者在沒有 kubeconfig / in-cluster identity 時，體驗會很差

## Implementation Handoff

下一步的 implementation plan 只需要處理：

- `kubernetes` dependency 與 package wiring
- client factory
- `RealKubernetesProviderAdapter`
- CLI `provider` mode
- 對應測試

先不要同時做多 cluster routing 或第二個 Kubernetes tool。
