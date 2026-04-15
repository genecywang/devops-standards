# OpenClaw Security Boundary

## 目標

定義 `OpenClaw` 在 alert auto-investigator 中的安全邊界，確保：

- 所有調查行為皆為 read-only
- agent 無法越權存取非目標系統
- 敏感資料不會被原樣回傳到 Slack
- 調查成本、延遲、失敗模式可控制

## 安全原則

- Least Privilege
- Fail Closed
- Deterministic Control Plane
- Tool Access Over Direct Access
- Auditable By Default
- Redact Before Reply

## 責任邊界

### 不交給 OpenClaw 的職責

- Slack event ingress
- ownership 判斷
- dedup / cooldown
- resolved handling
- rate limiting
- policy gate
- rollback / fallback 控制

### 交給 OpenClaw 的職責

- 根據 normalized event 規劃調查步驟
- 呼叫受控唯讀 tools
- 彙整調查結果
- 產出固定格式分析回覆

## Runtime 邊界

### Kubernetes Runtime

- 獨立 namespace
- 專屬 service account
- `runAsNonRoot: true`
- `allowPrivilegeEscalation: false`
- `readOnlyRootFilesystem: true`
- `seccompProfile: RuntimeDefault`
- drop all Linux capabilities
- 設定 requests / limits，避免 incident 時資源失控

### 禁止項目

- privileged container
- host networking
- hostPath mount
- shell access 給 agent
- 任意 outbound HTTP fetch

## Network 邊界

透過 `NetworkPolicy` 僅允許連線到：

- Slack API
- LLM API endpoint
- Prometheus endpoint
- kube-apiserver
- AWS API endpoint

預設 deny all 其他 egress。

## Identity 與權限

### AWS

- 使用專屬 IRSA role
- 不與其他 workload 共用 role
- 只給 read-only 權限

允許：

- `cloudwatch:Get*`
- `cloudwatch:Describe*`
- `rds:Describe*`
- `eks:Describe*`

不允許：

- `Put*`
- `Modify*`
- `Delete*`
- `Update*`
- `Start*`
- `Stop*`

條件限制：

- account allowlist
- region allowlist
- 能用 ARN pattern 限縮就限縮

### Kubernetes RBAC

只允許：

- `get/list/watch` on `pods`
- `get/list/watch` on `pods/log`
- `get/list/watch` on `events`
- `get/list/watch` on `deployments`
- `get/list/watch` on `replicasets`
- `get/list/watch` on `nodes`

禁止：

- `create/update/patch/delete`
- `exec`
- `port-forward`
- `secrets`

## Tool Boundary

`OpenClaw` 不應直接持有任意 AWS / K8s / Prometheus client 的自由查詢能力。

必須透過 tool wrapper 提供能力，每個 tool 都要實作：

- input schema validation
- scope validation
- timeout
- retry ceiling
- output truncation
- secret / sensitive pattern redaction
- audit log

### 最小 toolset 建議

- `describe_cloudwatch_alarm`
- `query_cloudwatch_metric`
- `describe_rds`
- `get_pod_status`
- `get_pod_events`
- `get_pod_logs`
- `describe_node`
- `query_prometheus`

### Tool 設計要求

- namespace allowlist
- region allowlist
- cluster allowlist
- `tail`、duration、range 等參數都要有上限
- 不允許 agent 組出任意 shell command

## Sensitive Data Boundary

### 必須 redact 的資料

- API keys
- bearer tokens
- passwords
- authorization headers
- session tokens
- 可能的 credentials pattern

### 需要審慎處理的資料

- internal hostnames
- internal endpoints
- 大段 raw logs
- stack traces 中的敏感參數

### Slack Reply 規則

- 不直接貼 raw tool output
- logs 只允許節錄
- 回覆長度有上限
- 需經 final redaction pass 才能回 Slack

## Execution Budget

每次 investigation 都必須有限額：

- `max_steps`
- `max_tool_calls`
- `max_duration_seconds`
- `max_output_tokens`
- 每個 tool 的 timeout
- 每個 tool 的 retry ceiling

預設超限行為：

- 停止 investigation
- 回傳 partial result 或 summarize-only

## Failure Handling

### OpenClaw timeout

- 停止 investigation
- 回 Slack 一則簡短 fallback 回覆
- 標記 investigation failed metric

### Tool timeout / permission denied

- 將 tool error 當成 evidence 回傳給 agent
- 可在預算內改查其他 tool
- 不可無限重試

### Slack reply 失敗

- 有限次 retry
- 失敗後只記 audit / error log

### 連續失敗

- 達閾值後自動降級成 summarize-only 或 skip

## Audit 與 Observability

每次 investigation 至少記錄：

- alert key
- source
- status
- tools called
- tool param summary
- duration
- result state
- error reason

注意：

- audit log 不記 secrets
- 不完整保留 raw logs
- 大輸出只保留摘要或 hash

## Shadow Mode

production 上線前，必須先經過 shadow mode。

### shadow mode 行為

- 收 alert
- 跑 control plane
- 可執行 investigation
- 不回正式 thread，或只回 private test channel

### exit criteria

- parser success rate 達標
- dedup 誤判率在容忍值內
- investigation success rate 達標
- P95 latency 可接受
- token / cost 在預算內
- 人工抽樣 review 正確率達標

## 驗收標準

- OpenClaw 僅能使用 read-only tools
- 無法直接執行 shell 或任意 HTTP
- 所有 tool 都有 scope / timeout / truncation / audit
- Slack 回覆前必經 redaction
- failure mode 有固定 fallback
- shadow mode 指標達標後才可正式 rollout
