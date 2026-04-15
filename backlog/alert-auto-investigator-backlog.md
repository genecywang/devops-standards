# OpenClaw Integration Backlog

## 目標

- 建立一個可控、可審計、read-only 的 Slack alert auto-investigator
- 告警來源先只支援 `CloudWatch Alarm` 與 `Alertmanager`
- `OpenClaw` 只負責 investigation plane，不負責 control plane
- production 導向，優先考慮安全邊界、fallback、可驗證性

## 非目標

- 不做自動修復
- 不做任意 Slack 對話式 chatbot
- 不一次支援所有告警類型
- 不把 dedup / ownership / resolved handling 交給 LLM

## 架構原則

- source adapter 先做最小正規化
- control plane 一律 deterministic
- `OpenClaw` 僅能使用受限、唯讀、可審計的 tools
- 調查結果固定格式回 Slack thread
- 任一環節失敗時，不能影響原始告警通知

## 核心資料流

1. `CloudWatch Alarm Lambda` / `Alertmanager template` 產生標準化事件
2. Slack 收到固定格式訊息
3. Investigator service 收 Slack event
4. parse 成 `NormalizedAlertEvent`
5. control plane 執行 prefilter / dedup / cooldown / policy
6. 符合條件才呼叫 `OpenClaw`
7. `OpenClaw` 使用受限 tools 執行 investigation
8. service 格式化結果並回覆 Slack thread
9. metrics / audit log 記錄全流程

## Backlog

### Phase 0：設計定稿

- [ ] 定義 `NormalizedAlertEvent v1`
- [ ] 定義 schema versioning 與 backward compatibility 規則
- [ ] 定義 Slack message contract
- [ ] 定義 Slack ingress model（Socket Mode / Events API）
- [ ] 定義 Slack event idempotency key 與 self-message filter strategy
- [ ] 定義 investigation policy
- [ ] 定義 `OpenClaw` tool allowlist
- [ ] 定義 response format
- [ ] 定義 fallback / rollback 行為
- [ ] 定義 audit log 與 metrics 欄位

### Phase 1：告警正規化

#### CloudWatch Alarm

- [ ] 定義 CloudWatch Alarm -> `NormalizedAlertEvent` mapping
- [ ] 定義 `status` 正規化規則：`ALARM -> firing`、`OK -> resolved`
- [ ] 定義 `region_code` 從 `AlarmArn` 抽取規則
- [ ] 定義 `resource_type` / `resource_name` 從 `Trigger.Dimensions` 映射規則
- [ ] 定義 `alert_key` 規則：`cloudwatch_alarm:{account_id}:{region_code}:{alarm_name}`
- [ ] 調整 Lambda 輸出固定 Slack 格式

#### Alertmanager

- [ ] 定義 Alertmanager -> `NormalizedAlertEvent` mapping
- [ ] 定義 `resource_type` / `resource_name` 推導規則
- [ ] 定義 `alert_key` 規則
- [ ] 調整 Alertmanager Slack template，輸出固定欄位

#### 測試

- [ ] 蒐集真實歷史告警樣本作為 fixtures
- [ ] 驗證 `status` / `alert_key` / `resource_name` 正確率
- [ ] 驗證 resolved 與 firing 分類穩定
- [ ] 定義缺欄位 / 未知 schema version 的 fail-close 或 summarize-only 行為

### Phase 2：Control Plane

- [ ] 忽略 bot 自己的訊息
- [ ] ownership 判斷
- [ ] dedup
- [ ] cooldown
- [ ] rate limit
- [ ] resolved handling
- [ ] flap handling
- [ ] investigate allowlist / denylist
- [ ] fallback response

#### Fallback 行為

- [ ] 定義 `OpenClaw` timeout 時改走 summarize-only
- [ ] 定義單一 tool timeout / error 時的繼續或中止策略
- [ ] 定義 Slack reply retry 與失敗後處理方式
- [ ] 定義連續 investigation failure 的自動降級策略

#### 初版 investigate allowlist

- [ ] `OOMKilled`
- [ ] `CrashLoopBackOff`
- [ ] `NodeNotReady`
- [ ] `HostOutOfMemory`
- [ ] `RDS ReadIOPS`
- [ ] `RDS CPUUtilization`
- [ ] `RDS FreeStorageSpace`

### Phase 3：OpenClaw 安裝與安全邊界

#### K8s Runtime

- [ ] 獨立 namespace
- [ ] 專屬 service account
- [ ] `runAsNonRoot: true`
- [ ] `allowPrivilegeEscalation: false`
- [ ] `readOnlyRootFilesystem: true`
- [ ] `seccompProfile: RuntimeDefault`
- [ ] drop all capabilities
- [ ] requests / limits

#### Network

- [ ] 建立 NetworkPolicy
- [ ] 僅允許連往 Slack API
- [ ] 僅允許連往 LLM API endpoint
- [ ] 僅允許連往 Prometheus endpoint
- [ ] 僅允許連往 AWS API endpoint
- [ ] 僅允許連往 kube-apiserver

#### Secrets

- [ ] Slack token 走 `ExternalSecrets`
- [ ] LLM API key 走 `ExternalSecrets`
- [ ] 不在 log / config 中暴露 secret

#### AWS IAM

- [ ] 建立專屬 IRSA role
- [ ] 只給 `cloudwatch:Get*`
- [ ] 只給 `cloudwatch:Describe*`
- [ ] 只給 `rds:Describe*`
- [ ] 只給 `eks:Describe*`
- [ ] 不給任何 write 權限
- [ ] 限制 account / region scope

#### Kubernetes RBAC

- [ ] `get/list/watch` on `pods`
- [ ] `get/list/watch` on `pods/log`
- [ ] `get/list/watch` on `events`
- [ ] `get/list/watch` on `deployments`
- [ ] `get/list/watch` on `replicasets`
- [ ] `get/list/watch` on `nodes`
- [ ] 不給 `create/update/patch/delete`
- [ ] 不給 `exec`
- [ ] 不給 `secrets`

#### Tool 安全邊界

- [ ] 所有 tool 做 input schema validation
- [ ] 所有 tool 做 scope validation
- [ ] 所有 tool 設 timeout
- [ ] 所有 tool 設 output truncation
- [ ] 所有 tool 做 sensitive data redaction
- [ ] 所有 tool 寫 audit log

#### Slack 輸出安全邊界

- [ ] 定義回 Slack 前的 final redaction policy
- [ ] 定義敏感 pattern 清單（token、password、authorization header 等）
- [ ] 定義 internal hostname / endpoint 顯示策略
- [ ] 定義最大回覆長度與 block 數
- [ ] 定義 raw logs / raw tool output 禁止直接貼出的規則

#### Investigation Budget

- [ ] `max_steps`
- [ ] `max_tool_calls`
- [ ] `max_duration_seconds`
- [ ] `max_output_tokens`
- [ ] tool error retry ceiling

### Phase 4：串接 OpenClaw

- [ ] 建立 `openclaw_runner`
- [ ] 定義 investigation request schema
- [ ] 傳入 normalized event
- [ ] 傳入 raw text / raw payload
- [ ] 傳入 allowed tools
- [ ] 傳入 execution budget
- [ ] 定義固定 response schema
- [ ] 整合 Slack thread reply

#### 回覆格式

- [ ] `What happened`
- [ ] `What I checked`
- [ ] `Likely cause`
- [ ] `Suggested next step`
- [ ] `Confirmed / Hypothesis / Not verified` 標示規則

### Phase 5：測試計劃

#### Normalization

- [ ] CloudWatch `ALARM`
- [ ] CloudWatch `OK`
- [ ] Alertmanager `firing`
- [ ] Alertmanager `resolved`

#### Control Plane

- [ ] dedup test
- [ ] cooldown test
- [ ] rate limit test
- [ ] flap test
- [ ] allowlist / denylist test

#### Tool 層

- [ ] AWS describe success / timeout / permission denied
- [ ] Kubernetes log query success / not found
- [ ] Prometheus query success / empty / timeout

#### E2E

- [ ] `HostOutOfMemory`
- [ ] `CrashLoopBackOff`
- [ ] `RDS ReadIOPS`
- [ ] resolved event
- [ ] verify tool usage within budget
- [ ] verify Slack reply format

#### Staging Trigger

- [ ] 建立 staging 測試用 CloudWatch Alarm
- [ ] 觸發 staging Alertmanager test alert
- [ ] 優先使用 replay fixtures / synthetic alerts 驗證流程
- [ ] 僅對少數 case 做有限度真實觸發
- [ ] 驗證從來源到 Slack thread reply 的全流程

### Phase 6：Observability 與 Audit

- [ ] `alerts_received_total`
- [ ] `alerts_processed_total{action}`
- [ ] `investigation_started_total`
- [ ] `investigation_completed_total`
- [ ] `investigation_failed_total`
- [ ] `tool_calls_total{tool}`
- [ ] `tool_call_duration_seconds`
- [ ] `llm_tokens_total{direction}`
- [ ] `dedup_skipped_total`
- [ ] `rate_limited_total`

#### Audit Log

- [ ] alert key
- [ ] source
- [ ] status
- [ ] tools called
- [ ] tool params summary
- [ ] duration
- [ ] result state
- [ ] error reason
- [ ] secret-safe / truncated logging

### Phase 7：部署策略

- [ ] local fixture tests
- [ ] staging dry-run
- [ ] staging real alert tests
- [ ] production shadow mode
- [ ] production limited allowlist rollout
- [ ] production expand coverage after observation

#### Shadow Mode Exit Criteria

- [ ] 定義 parser success rate 門檻
- [ ] 定義 dedup 誤判率容忍值
- [ ] 定義 investigation success rate 門檻
- [ ] 定義 P95 latency 目標
- [ ] 定義每日 token / cost 上限
- [ ] 定義人工抽樣 review 正確率門檻

## 建議實作順序

1. 定義 `NormalizedAlertEvent v1`
2. 完成 CloudWatch Alarm normalizer
3. 完成 Alertmanager normalizer
4. 完成 control plane
5. 完成最小 toolset
6. 完成 `openclaw_runner`
7. 完成 Slack thread response
8. 完成 audit / metrics
9. 完成 staging e2e
10. 進 production shadow mode

## 第一版驗收標準

- CloudWatch Alarm 與 Alertmanager 都可轉成同一 schema
- resolved event 不會誤進 investigation
- dedup / cooldown 可穩定運作
- `OpenClaw` 只能使用 read-only tools
- 所有 tool 均有 timeout / truncation / audit
- Slack thread reply 格式固定
- staging 至少驗證 3 種高價值 alert
- production 可先以 shadow mode 觀察 1 週
