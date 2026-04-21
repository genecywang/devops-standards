# Alert Investigation Analysis Layer MVP Design

## Goal

在既有 `alert_auto_investigator` deterministic investigation flow 與
`assist/` shadow integration 基礎上，擴充一層
**bounded、single-call、provider-neutral、audit-first** 的
LLM analysis layer，讓 Slack reply 不只回傳目前狀態，還能提供保守、
可追溯的 incident interpretation。

這一版的目標不是做 autonomous investigator，也不是讓 LLM 自己決定要跑
哪些 tools，而是建立一個足夠小、可控、可替換 provider 的 analysis contract。

---

## Why This Phase Exists

目前專案已經完成：

- alert ingress / parsing
- deterministic normalization
- control gating
- rule-based dispatcher
- bounded Kubernetes / AWS investigation tools
- deterministic Slack reply
- `ReadonlyAssistService.after_investigation()` shadow hook
- `assist_mode=off|shadow` config 與 handler 接線
- `ElastiCache phase 1` merge、deploy 與真實 dev alarm 驗證

這代表 investigation runtime 已經可用，當前缺口不再是「能不能查到 evidence」，
而是「能不能把 evidence 轉成值班者可立即採取行動的判讀」。

現在的 deterministic reply 已能說明：

- target 是誰
- current state 是什麼
- primary reason 是什麼

但仍欠缺：

- 這代表什麼
- 應不應該立即升級處理
- 下一步先查哪裡
- 哪些地方其實證據不足，不能亂下結論

這正是 analysis layer 的價值。

---

## Scope

### In Scope

- 在 successful deterministic investigation 之後，擴充既有 assist hook 為單次 LLM analysis call
- analysis input 只允許使用：
  - `NormalizedAlertEvent`
  - `CanonicalResponse.summary`
  - `CanonicalResponse.metadata`
  - `CanonicalResponse.evidence`
  - `CanonicalResponse.enrichment`
- analysis output 使用固定結構化 schema
- provider-neutral backend interface
- mode 從既有 `off|shadow` 擴充為 `off|shadow|visible`
- analysis invocation audit contract
- Slack reply 可附加 analysis 區塊

### Out Of Scope

- multi-step tool planning
- LLM 自行決定額外呼叫 Kubernetes / AWS tools
- cross-incident memory
- incident history RAG
- autonomous remediation
- provider routing / fallback orchestration
- `openclaw_foundation` rename
- root cause confirmed wording
- daily / monthly spend enforcement

---

## Core Design Choice

採用 **single-call bounded analysis**，而不是 agent loop。

### Relationship To Existing `ReadonlyAssistService`

這一版 **不另起第二套平行 service / mode / hook**。

設計決策如下：

- 保留既有 `ReadonlyAssistService` integration point
- 保留既有 `assist_mode` config family
- 逐步把現有 `ReadonlyAssistBackend` 擴充成 provider-neutral analysis backend
- `analysis layer` 是產品設計用語，不代表另建一個與 `assist/` 平行的 package

因此這一版的實作方向應為：

- 擴充現有 `assist/` 模組
- 調整 payload / response contract
- 新增 provider adapter
- handler 繼續透過既有 `assist_service.after_investigation(...)` 觸發

明確不做：

- 新建第二套 `AnalysisService` 與 `ReadonlyAssistService` 並存
- 新建第二套 mode config 與 assist mode 並存
- 先廢棄 assist 再平地重建 analysis package

### Why Not Summarization Only

純 summarization 只能把 evidence 改寫成人話，對值班者的提升有限。

這一版要提供的價值不只是「更好讀」，而是：

- current interpretation
- recommended next step
- confidence and caveats

### Why Not Agent Loop

目前 evidence 與 runtime 還不適合 agent loop：

- `ExecutionBudget` 明顯是為 bounded investigation 設計
- dispatcher 仍是單一 `resource_type -> tool_name`
- 現有 evidence 以 current-state facts 為主，不是 RCA-ready evidence chain
- 多步 tool orchestration 會顯著提高成本、不可控性與 audit 複雜度

所以這一版應明確維持：

- one investigation
- one analysis call
- one bounded response contract

---

## Evidence Sufficiency Boundary

### Confirmed Product Assumption

目前工具輸出的資訊，足以支持：

- current state interpretation
- risk framing
- conservative next-step guidance

目前工具輸出的資訊，不足以穩定支持：

- confirmed root cause
- cross-system blame assignment
- metric trend causality
- deployment history correlation
- log-based diagnosis

### Hard Safety Rule

analysis layer **不得**把推測寫成定論。

若沒有下列其中一種 evidence，不得聲稱 root cause 已確認：

- metric history
- log evidence
- cross-resource correlation evidence
- deployment / config change evidence

因此第一版輸出必須明確區分：

- `confirmed_observations`
- `current_interpretation`
- `recommended_next_step`
- `caveats`

任何帶有推測性的判讀，都只能落在 interpretation 或 caveat，
不能落在 confirmed observation。

---

## Architecture

### Existing Flow

目前產品流程為：

1. Slack event ingress
2. alert parsing
3. control pipeline
4. deterministic dispatch
5. bounded tool execution
6. deterministic reply formatting

### Proposed Flow

新增後的流程為：

1. Slack event ingress
2. alert parsing
3. control pipeline
4. deterministic dispatch
5. bounded tool execution
6. optional analysis invocation
7. deterministic reply formatting with optional analysis section

Analysis layer 只消費 deterministic investigation 結果，不直接碰 tool registry。

---

## Provider-Neutral Contract

上層 product logic 不應直接依賴 OpenAI 或 Anthropic SDK。

應在既有 `assist/` 骨架內自定義 provider-neutral contract：

- request payload schema
- response payload schema
- usage payload schema
- backend protocol
- analysis error model

命名上可沿用 `ReadonlyAssistBackend` / `ReadonlyAssistService`，但 contract
內容需升級為 analysis-ready 結構，避免 assist 與 analysis 各有一套 protocol。

### Required Request Inputs

analysis request payload 最低應包含：

- alert context
- canonical summary
- bounded evidence
- metadata
- output schema version
- prompt version
- max output tokens
- analysis mode

### Required Response Fields

analysis response payload 最低應包含：

- `summary`
- `current_interpretation`
- `recommended_next_step`
- `confidence`
- `caveats`
- provider metadata
- model identifier
- token / latency usage

### Output Shape

第一版建議的邏輯輸出欄位為：

- `summary`
- `current_interpretation`
- `recommended_next_step`
- `confidence`
- `caveats`

可選擇再加：

- `confirmed_observations`

但不要加過多欄位，避免 prompt / parsing 複雜化。

---

## Slack Presentation

第一版不應直接把 deterministic reply 替換成 AI reply。

建議保留現有 deterministic 區塊，AI analysis 以附加段落呈現。

建議區塊命名：

- `*AI Analysis*`

區塊必須帶明確 disclaimer，至少包含：

- `AI-generated`
- `verify before acting`

內容依序呈現：

- summary
- current interpretation
- recommended next step
- confidence
- caveats

建議 `confidence` 顯示在區塊前段，而不是埋在最後一行。

### Shadow Mode

在 `shadow` mode：

- analysis 會執行
- 結果只記 audit / logs
- 不附加到 Slack reply

### Visible Mode

在 `visible` mode：

- analysis 會執行
- 成功結果附加到 Slack reply
- 若 analysis 失敗，不得影響 deterministic reply

### Mode Compatibility

現有 config 僅支援：

- `off`
- `shadow`

這一版需明確擴充為：

- `off`
- `shadow`
- `visible`

相容策略：

- 現有 `OPENCLAW_READONLY_ASSIST_MODE=off|shadow` 必須繼續有效
- 新增 `visible` 時，舊環境若未設定，預設仍為 `off`
- production rollout 預設停在 `shadow`
- `visible` 必須可由單一 mode config 立即關閉，作為 kill switch

---

## Audit Requirements

目前 `openclaw_foundation.runtime.audit` 過於薄弱，無法支撐 analysis layer。

第一版 analysis audit 必須至少記錄：

- `request_id`
- `alert_key`
- `resource_type`
- `resource_name`
- `tool_name`
- `provider`
- `model`
- `prompt_version`
- `analysis_mode`
- `latency_ms`
- `input_tokens`
- `output_tokens`
- `analysis_result_state`
- `response_digest`

### Audit Placement

這一版不應直接把 analysis audit 強塞進現有
`openclaw_foundation.runtime.AuditEvent`，原因如下：

- 現有欄位寫死 `cluster` / `namespace`
- AWS investigation 與 analysis invocation 不天然適配這個 shape
- 直接擴充既有 dataclass 會引入 foundation API 變更與 debt 混修

因此設計決策為：

- 保留既有 `openclaw_foundation.runtime.AuditEvent` 不動
- 在 `alert_auto_investigator.assist` 範圍新增 analysis-specific audit event
- foundation audit debt 另開後續工作，不與此 spec 綁定

### `response_digest`

`response_digest` 的定義必須固定為：

- 對 redacted 後的 analysis response 進行 canonical JSON serialization
- 再做 `sha256`

Digest 不得直接包含 raw response text，也不得基於未 redacted payload 計算。

### Audit Purpose

這些欄位不是 best-effort diagnostics，而是為了：

- production traceability
- prompt / model change impact review
- token cost review
- failure analysis
- later provider comparison

---

## Failure Handling

analysis failure 必須 fail-open。

若 analysis provider 出現：

- timeout
- rate limit
- provider API failure
- malformed structured output

系統應：

- 保留原 deterministic investigation reply
- 記錄 analysis audit event
- 不中斷主 handler flow

### Expected Error Classes

建議至少定義：

- `AnalysisTimeoutError`
- `AnalysisRateLimitError`
- `AnalysisProviderError`
- `AnalysisSchemaError`

上層不得直接處理 provider-specific exception。

---

## Input Redaction And Data Boundary

analysis provider 收到的 payload 必須來自 **redacted and bounded** investigation output。

硬規則：

- 不得把未 redacted raw evidence 直接送給 provider
- 若 `CanonicalResponse.redaction_applied` 為 `False`，analysis 不得送出，應記錄 failure
- analysis request builder 必須只消費 redacted summary / metadata / evidence

這一版不要求解決所有資料分類問題，但必須確保：

- IP
- token-like strings
- obvious secret patterns

至少延續既有 redaction 邏輯，不可繞過。

---

## Provider Call Budget

analysis layer 是付費能力，第一版必須有明確硬上限。

### Required Limits

- 每次 analysis call 必須有 timeout
- 每次 analysis call 必須限制 input token 上限
- 每次 analysis call 必須限制 output token 上限
- 不做 automatic retry；第一次失敗即 fail-open

### Recommended Defaults

- timeout: `10` 秒
- input token ceiling: `4000`
- output token ceiling: `500`

daily / monthly spend guard 本身不在這一版範圍內，但 spec 明確要求 audit
資料足以支持事後成本 review。

---

## Configuration And Rollout

第一版應至少支援三種模式：

- `off`
- `shadow`
- `visible`

### Off

- 不執行 analysis
- 保持現狀

### Shadow

- 執行 analysis
- 只 audit，不顯示到 Slack
- 用於 dev / staging 驗證 prompt 品質與 token cost

### Visible

- 執行 analysis
- 成功則附加 analysis 到 Slack
- 失敗時回退 deterministic reply

---

## Prompt And Schema Governance

第一版至少需要兩個版本欄位：

- `prompt_version`
- `output_schema_version`

治理規則：

- prompt 應以 repo 內可版本控制的常數或 template 檔存在
- output schema 版本必須與 parser / validator 綁定
- schema 變更時必須升版，不能沿用舊版識別值

這兩個欄位不只是 audit decoration，而是之後做 prompt regression 與 provider
比較的基礎。

---

## Testing Strategy

### Unit Tests

需要覆蓋：

- request builder 只使用允許的 evidence 欄位
- provider adapter 將 provider-specific response 映射為統一 response
- malformed analysis output 觸發 schema error
- analysis failure 不影響 deterministic reply
- visible / shadow / off mode 行為不同

### Integration Tests

需要覆蓋：

- handler 在 `shadow` mode 觸發 analysis 但不附加 Slack 區塊
- handler 在 `visible` mode 成功附加 AI analysis
- provider failure 時仍保留既有 reply

### Prompt / Output Regression

建議以 golden-style structured output fixture 驗證：

- healthy but alarming metric case
- gone / not found case
- degraded infrastructure case
- insufficient evidence case

---

## Non-Goals For This Phase

這一版明確不做：

- tool-use loop
- autonomous investigation planning
- multi-provider dynamic routing
- incident memory
- cross-alert similarity
- remediation recommendations beyond safe next-step guidance

若未來要做上述能力，必須另開新 spec。

---

## Success Criteria

這一版完成時，應達成：

- deterministic investigation reply 仍完整保留
- analysis layer 可由 config 開關控制
- 同一份 bounded evidence 可透過 provider-neutral contract 送到不同 provider
- analysis 失敗不影響主 investigation flow
- audit 可回溯每次 analysis invocation
- AI output 不會把推測寫成 confirmed root cause

---

## Recommended Next Step

此 spec 核准後，下一步應寫 implementation plan，任務順序建議為：

1. analysis contract 與錯誤模型
2. provider-neutral service 與 fake provider
3. handler / formatter integration with `off` / `shadow` / `visible`
4. audit contract and logging
5. provider adapter implementation
6. focused regression and rollout notes
