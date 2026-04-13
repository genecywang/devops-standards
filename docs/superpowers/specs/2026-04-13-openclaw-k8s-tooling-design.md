# OpenClaw Kubernetes Tooling Design

## Objective

在既有 `openclaw_foundation/` Python skeleton 上，擴充第一個真實 read-only tool：`get_pod_status`，同時把 `security + tool layer` 所需的最小 guardrail 掛進 runtime / tool execution path。

這一版的目標不是完成整套 Kubernetes integration，而是建立一個可替換的 provider adapter 邊界，並驗證下列控制點能一起工作：

- scope validation
- timeout
- truncation
- redaction
- audit hook

## Scope

這一版只包含：

- Kubernetes provider adapter abstraction
- 一個真實 read-only `get_pod_status` tool
- namespace / cluster scope validation
- tool timeout boundary
- response truncation
- redaction hook
- audit event hook
- 對應測試

## Non-Goals

這一版不做：

- write action
- Slack integration
- 多 tool orchestration
- 真實 audit sink persistence
- 真 metrics backend
- Prometheus / AWS provider
- Kubernetes exec / logs / events tools

## Proposed Layout

新增或擴充：

```text
openclaw_foundation/
  src/openclaw_foundation/
    adapters/
      __init__.py
      kubernetes.py
    runtime/
      audit.py
      guards.py
    tools/
      kubernetes_pod_status.py
  tests/
    test_kubernetes_tool.py
    test_runtime_guards.py
```

## Core Flow

第一個真實 read-only flow：

1. runner 收到 investigation request
2. tool layer 驗證 request scope 是否包含允許的 `cluster` / `namespace`
3. tool layer 套用 timeout boundary
4. `get_pod_status` 呼叫 Kubernetes provider adapter
5. adapter 回傳 pod status payload
6. tool layer 做 truncation
7. tool layer 做 redaction
8. runtime 發出 audit event
9. runner 回 canonical response

## Design Decisions

### 1. Provider Adapter First

這次不把 Kubernetes client call 直接寫死在 tool 裡，而是透過 adapter。

原因：

- 後面 `get_pod_logs`、`get_pod_events`、`describe_node` 都能重用同一層
- tool implementation 可以只關心 input / output contract 與 guardrail
- 後續測試可用 fake adapter 替代真 client

### 2. Read-Only Single Tool First

第一版只接 `get_pod_status`。

原因：

- 可以先驗證 K8s read-only boundary 是否成立
- 比 log / events 更容易控制 truncation 與 redaction
- 先避免把 raw log 敏感資訊處理拉進來

### 3. Guardrails Before More Tools

先把 guardrail 層做出來，再擴更多 tool。

原因：

- 沒有 scope validation / timeout / truncation / redaction / audit hook，後續每接一個 tool 都會重複修
- 這一層才是 foundation 的核心價值，不是單一 API call

## Interfaces

### Kubernetes Provider Adapter

至少提供：

- `get_pod_status(cluster: str, namespace: str, pod_name: str) -> dict`

第一版可以先有兩種實作路徑：

- 真實 Kubernetes client adapter
- test 用 fake adapter

### Tool Input

`get_pod_status` 至少需要：

- `cluster`
- `namespace`
- `pod_name`

### Tool Output

最小輸出應只包含必要欄位，例如：

- `pod_name`
- `namespace`
- `phase`
- `container_statuses`
- `node_name`

不應直接回整份 unbounded raw pod object。

### Guardrail Hooks

至少要有：

- `validate_scope(...)`
- `run_with_timeout(...)`
- `truncate_output(...)`
- `redact_output(...)`
- `build_audit_event(...)`

## Scope Rules

第一版先固定：

- request 未帶 `cluster` -> deny
- request 未帶 `namespace` -> deny
- `namespace` 不在 allowlist -> deny
- `cluster` 不在 allowlist -> deny

allowlist 可以先用程式內 config / fixture 注入，不急著做 production-ready config loader。

## Timeout / Truncation / Redaction Rules

### Timeout

- 單次 tool call 需有明確 timeout
- timeout 後回 canonical failed / partial path，不可無限等待

### Truncation

- 不回傳完整 pod object
- 只保留最小 status fields
- container status 若過長需截斷

### Redaction

- 移除或遮罩敏感 annotation / env-like patterns
- 不直接暴露可能的 token / credential 字串

### Audit

audit hook 至少記錄：

- `request_id`
- `tool_name`
- `cluster`
- `namespace`
- `result_state`
- `error_reason`（若有）

## Testing

至少需要：

- scope validation test
- timeout behavior test
- truncation test
- redaction test
- adapter-backed `get_pod_status` success path test
- runner integration test with the real tool wired through registry

## Acceptance Criteria

完成時應能：

- 在 `openclaw_foundation/` 內註冊一個真實 `get_pod_status` tool
- 用 fake adapter 跑完整 success path 測試
- 明確驗證 unauthorized cluster / namespace 會 fail closed
- tool output 不會回 unbounded raw pod payload
- audit hook 會產生結構化事件
- 後續新增第二個 Kubernetes read-only tool 時，不需要重拆 adapter 與 guardrail 邊界

## Risks

- 如果直接把 Kubernetes client call 寫進 tool，本輪之後擴更多 tool 會快速重複
- 如果不先固定最小輸出 contract，之後很容易把 raw pod object 直接向上層洩漏
- 如果先做真 cluster 整合但不做 fake adapter 測試，後面很難穩定驗證 timeout / scope deny 路徑

## Implementation Handoff

下一步應寫 implementation plan，只處理：

- adapter interface
- guardrail hooks
- `get_pod_status` tool
- fake adapter tests
- runner wiring

先不要同時接第二個 provider 或第二個 Kubernetes tool。
