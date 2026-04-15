# Platform Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將 `Platform Foundation` 從 backlog 梳理成可執行的共用底座 implementation package，先在本 repo 固化 contracts、runtime boundary、security control、observability 與 rollout 設計，供後續 `OpenClaw` 程式碼與 infra repo 實作。

**Architecture:** Foundation 採文件先行，將共用能力拆成 `contracts`、`runtime`、`tool layer`、`security`、`observability`、`rollout` 六個 execution tracks。此 plan 只處理兩條產品線共用底座，不包含 source-specific ingress parser、alert playbook 或 self-service command catalog。

**Tech Stack:** Markdown、Git、OpenClaw domain contracts、AWS IAM / IRSA、Kubernetes RBAC / NetworkPolicy、Prometheus metrics、Slack event model

---

## File Structure

本次 implementation 先在本 repo 建立以下文件結構：

- `docs/platform-foundation/README.md`
  說明 foundation scope、non-goals、track dependency、交付順序。
- `docs/platform-foundation/contracts.md`
  定義 config model、scope model、Slack ingress envelope、response envelope、audit schema、metrics schema。
- `docs/platform-foundation/runtime.md`
  定義 `openclaw_runner`、request schema、execution budget、tool registration、timeout / retry / cancellation、fallback mode。
- `docs/platform-foundation/tool-layer.md`
  定義 AWS / Kubernetes / Prometheus wrapper base、validation、scope enforcement、timeout、truncation、audit、redaction hooks。
- `docs/platform-foundation/security.md`
  定義 namespace、service account、IRSA、RBAC、NetworkPolicy、ExternalSecrets、non-production write boundary。
- `docs/platform-foundation/observability.md`
  定義 metrics、audit pipeline、failure taxonomy、token / cost tracking、dashboard 與 alerting 需求。
- `docs/platform-foundation/rollout.md`
  定義 local fixtures、staging dry-run、shadow mode、exit criteria、production rollout checklist。
- `backlog/platform-foundation-backlog.md`
  轉成對應文件與 track 的 backlog 索引，避免 backlog 與 implementation docs 脫節。

## Implementation Rules

- `Platform Foundation` 僅處理共用底座，不納入 `NormalizedAlertEvent` parser 實作與 source-specific mapping。
- production 一律以 read-only investigation boundary 為前提，write action 只保留 non-production boundary 設計，不做 production write 擴權。
- 所有 contract 必須標示 required / optional fields、validation rule、deny behavior、owner。
- 所有 track 都要有明確 dependency、驗證指令、完成定義。
- 本 repo 先完成文件與驗收框架；真正的 service / infra repo implementation 必須以這批文件為準。

### Task 1: Establish Foundation Document Skeleton

**Files:**
- Create: `docs/platform-foundation/README.md`
- Create: `docs/platform-foundation/contracts.md`
- Create: `docs/platform-foundation/runtime.md`
- Create: `docs/platform-foundation/tool-layer.md`
- Create: `docs/platform-foundation/security.md`
- Create: `docs/platform-foundation/observability.md`
- Create: `docs/platform-foundation/rollout.md`
- Modify: `backlog/platform-foundation-backlog.md`
- Test: `README.md`

- [ ] **Step 1: Create the foundation directory and overview document**

```markdown
# Platform Foundation

## Scope

- Shared contracts for `Alert Auto-Investigator` and `Self-Service Ops Copilot`
- Shared runtime boundary for `OpenClaw`
- Shared tool enforcement and policy controls
- Shared audit, metrics, rollout, and verification rules

## Non-Goals

- Source-specific event parser implementation
- Alert investigation playbook logic
- Self-service command catalog
- Production write actions

## Execution Tracks

1. Contracts
2. Runtime
3. Tool Layer
4. Security
5. Observability
6. Rollout

## Dependency Order

`contracts` -> `runtime` -> `tool-layer` -> `security` -> `observability` -> `rollout`
```

- [ ] **Step 2: Create one markdown file per execution track with a fixed section layout**

```markdown
# <Track Name>

## Objective

## In Scope

## Out of Scope

## Inputs and Dependencies

## Decisions

## Validation Rules

## Deliverables

## Exit Criteria

## Open Questions
```

- [ ] **Step 3: Link the overview from the repository entry point**

```markdown
## Planning

- [Platform Foundation](docs/platform-foundation/README.md)
```

Run: `rg -n "Platform Foundation" README.md docs/platform-foundation/README.md`
Expected: 2 matches, one in `README.md`, one in `docs/platform-foundation/README.md`

- [ ] **Step 4: Re-index the backlog entry so it points to document tracks instead of only phase bullets**

```markdown
## 實作文件對應

- `docs/platform-foundation/contracts.md`
- `docs/platform-foundation/runtime.md`
- `docs/platform-foundation/tool-layer.md`
- `docs/platform-foundation/security.md`
- `docs/platform-foundation/observability.md`
- `docs/platform-foundation/rollout.md`
```

- [ ] **Step 5: Verify the document skeleton exists**

Run: `test -f docs/platform-foundation/README.md && test -f docs/platform-foundation/contracts.md && test -f docs/platform-foundation/runtime.md && test -f docs/platform-foundation/tool-layer.md && test -f docs/platform-foundation/security.md && test -f docs/platform-foundation/observability.md && test -f docs/platform-foundation/rollout.md && echo OK`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add README.md backlog/platform-foundation-backlog.md docs/platform-foundation
git commit -m "docs: scaffold platform foundation plan docs"
```

### Task 2: Define Shared Contracts

**Files:**
- Modify: `docs/platform-foundation/contracts.md`
- Reference: `backlog/platform-foundation-backlog.md`
- Reference: `backlog/normalized-alert-event-v1.md`
- Reference: `backlog/openclaw-security-boundary.md`
- Test: `docs/platform-foundation/contracts.md`

- [ ] **Step 1: Write the contract objective and scope boundary**

```markdown
## Objective

Define the shared contracts that every `Platform Foundation` consumer must implement before any runtime or tool execution starts.

## In Scope

- Common config model
- Environment / account / region / cluster scoping model
- Slack ingress envelope
- Shared response envelope
- Audit schema
- Metrics schema

## Out of Scope

- `NormalizedAlertEvent` source mapping
- Alert ownership logic implementation
- Product-specific Slack copywriting
```

- [ ] **Step 2: Define the common config and scoping model explicitly**

```markdown
## Decisions

### Config Model

| Field | Type | Required | Description |
|---|---|---|---|
| `environment` | string | yes | logical environment such as `staging`, `test`, `prod-jp` |
| `account_allowlist` | list[string] | yes | permitted AWS accounts |
| `region_allowlist` | list[string] | yes | permitted AWS regions |
| `cluster_allowlist` | list[string] | no | permitted Kubernetes clusters |
| `namespace_allowlist` | list[string] | no | permitted namespaces |
| `mode` | string | yes | `read_only`, `non_prod_write`, `shadow` |
| `max_steps` | integer | yes | investigation or execution step ceiling |
| `max_tool_calls` | integer | yes | total tool call ceiling |
| `max_duration_seconds` | integer | yes | run timeout ceiling |
| `max_output_tokens` | integer | yes | reply size ceiling |

### Scope Deny Rules

- missing `environment` -> deny ownership-sensitive execution
- target account not in `account_allowlist` -> deny
- target region not in `region_allowlist` -> deny
- `mode=read_only` with write intent -> deny
```

- [ ] **Step 3: Define the Slack ingress envelope and response envelope**

```markdown
### Slack Ingress Envelope

| Field | Type | Required | Description |
|---|---|---|---|
| `request_id` | string | yes | stable request id |
| `channel_id` | string | yes | Slack channel id |
| `thread_ts` | string | yes | Slack thread timestamp |
| `source_product` | string | yes | `alert_auto_investigator` or `self_service_ops_copilot` |
| `actor_type` | string | yes | `system`, `user`, `service` |
| `actor_id` | string | yes | Slack user id or service id |
| `payload_type` | string | yes | `alert_event`, `chat_command`, `thread_follow_up` |
| `payload_ref` | string | yes | source object key or normalized id |

### Shared Response Envelope

| Field | Type | Required | Description |
|---|---|---|---|
| `request_id` | string | yes | copied from ingress |
| `result_state` | string | yes | `success`, `partial`, `denied`, `failed`, `fallback` |
| `summary` | string | yes | short human-readable summary |
| `evidence_items` | list[object] | no | structured evidence snippets |
| `actions_attempted` | list[string] | yes | tool or decision summary |
| `redaction_applied` | boolean | yes | final output redaction status |
| `audit_ref` | string | yes | audit event key |
```

- [ ] **Step 4: Define audit and metrics schemas with owner and retention notes**

```markdown
### Audit Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `request_id` | string | yes | run identifier |
| `source_product` | string | yes | consumer product |
| `status` | string | yes | final state |
| `tool_names` | list[string] | yes | tools invoked during the run |
| `tool_param_summary` | list[string] | yes | redacted parameter summary |
| `duration_ms` | integer | yes | end-to-end duration |
| `error_reason` | string | no | normalized failure reason |
| `policy_denied` | boolean | yes | whether policy gate denied a step |

### Metrics Schema

- `openclaw_runs_total{source_product,result_state}`
- `openclaw_failures_total{source_product,error_reason}`
- `tool_calls_total{tool_name,result}`
- `tool_call_duration_seconds{tool_name}`
- `openclaw_tokens_total{source_product,model}`
- `redaction_hits_total{pattern_type}`
- `policy_denied_total{source_product,reason}`
```

- [ ] **Step 5: Verify all contract sections exist and required tables are present**

Run: `rg -n "^## Objective|^## In Scope|^## Out of Scope|^## Inputs and Dependencies|^## Decisions|^## Validation Rules|^## Deliverables|^## Exit Criteria" docs/platform-foundation/contracts.md`
Expected: 8 matches

- [ ] **Step 6: Commit**

```bash
git add docs/platform-foundation/contracts.md
git commit -m "docs: define platform foundation shared contracts"
```

### Task 3: Define Runtime Core

**Files:**
- Modify: `docs/platform-foundation/runtime.md`
- Reference: `docs/platform-foundation/contracts.md`
- Reference: `backlog/openclaw-security-boundary.md`
- Test: `docs/platform-foundation/runtime.md`

- [ ] **Step 1: Define the runtime objective, owner, and non-goals**

```markdown
## Objective

Define a deterministic runtime boundary for `openclaw_runner` so product teams integrate through stable request / response contracts instead of ad hoc agent execution.

## In Scope

- `investigation_request`
- `execution_request`
- `execution_budget`
- tool registration contract
- retry / timeout / cancellation rules
- fallback behavior

## Out of Scope

- LLM prompt wording
- source-specific event normalization
- product-specific Slack thread UX
```

- [ ] **Step 2: Define the request schemas and execution budget**

````markdown
## Decisions

### Investigation Request

```json
{
  "request_type": "investigation",
  "request_id": "req-123",
  "source_product": "alert_auto_investigator",
  "scope": {
    "environment": "prod-jp",
    "account_id": "123456789012",
    "region_code": "ap-northeast-1",
    "cluster": "prod-jp-main"
  },
  "input_ref": "normalized-alert-event:cloudwatch_alarm:...",
  "budget": {
    "max_steps": 6,
    "max_tool_calls": 8,
    "max_duration_seconds": 45,
    "max_output_tokens": 1200
  }
}
```

### Execution Request

```json
{
  "request_type": "execution",
  "request_id": "req-456",
  "source_product": "self_service_ops_copilot",
  "scope": {
    "environment": "staging",
    "cluster": "staging-main",
    "namespace": "payments"
  },
  "requested_action": "rollout_restart",
  "approval_state": "approved",
  "budget": {
    "max_steps": 4,
    "max_tool_calls": 4,
    "max_duration_seconds": 30,
    "max_output_tokens": 800
  }
}
```
````

- [ ] **Step 3: Define runtime state transitions and failure handling**

```markdown
### Runtime State Machine

1. `received`
2. `validated`
3. `policy_checked`
4. `executing`
5. `redacting`
6. `completed`

### Failure Rules

- validation failure -> `denied`
- policy failure -> `denied`
- budget exceeded -> `fallback`
- tool timeout after retry ceiling -> `partial`
- final redaction failure -> `failed`
```

- [ ] **Step 4: Define the tool registration contract and fallback mode**

```markdown
### Tool Registration Contract

Each tool must declare:

- `tool_name`
- `supported_request_types`
- `scope_requirements`
- `input_schema_ref`
- `timeout_seconds`
- `retry_ceiling`
- `redaction_profile`
- `audit_param_fields`

### Fallback Mode

- stop new tool execution
- summarize only from collected evidence
- mark response `result_state=fallback`
- emit `openclaw_failures_total{error_reason="budget_exceeded"}` when caused by budget limit
```

- [ ] **Step 5: Verify the runtime document contains request examples and the state machine**

Run: `rg -n "investigation_request|execution_request|Runtime State Machine|Fallback Mode|Tool Registration Contract" docs/platform-foundation/runtime.md`
Expected: 5 matches

- [ ] **Step 6: Commit**

```bash
git add docs/platform-foundation/runtime.md
git commit -m "docs: define platform foundation runtime core"
```

### Task 4: Define Tool Enforcement Layer

**Files:**
- Modify: `docs/platform-foundation/tool-layer.md`
- Reference: `docs/platform-foundation/contracts.md`
- Reference: `docs/platform-foundation/runtime.md`
- Reference: `backlog/openclaw-security-boundary.md`
- Test: `docs/platform-foundation/tool-layer.md`

- [ ] **Step 1: Define the tool layer objective and mandatory enforcement points**

```markdown
## Objective

Define a mandatory wrapper contract so every AWS, Kubernetes, and Prometheus tool enforces validation, scope checks, timeout, truncation, audit logging, and redaction in the same order.

## Validation Rules

Tool execution order must be:

1. input schema validation
2. scope validation
3. timeout budget allocation
4. upstream call execution
5. output truncation
6. redaction pass
7. audit emission
```

- [ ] **Step 2: Define the base wrapper contract for each provider**

```markdown
## Decisions

### AWS Wrapper Base

- accepts only explicit operation ids such as `describe_cloudwatch_alarm`
- forbids free-form AWS API operation names
- requires `account_id` and `region_code`

### Kubernetes Wrapper Base

- accepts only explicit verbs and resource types from allowlist
- forbids `exec`, `port-forward`, `secrets`
- requires `cluster` and `namespace` when namespaced

### Prometheus Wrapper Base

- accepts only approved query templates or bounded parameterized expressions
- requires explicit time range ceiling
- forbids unbounded raw range queries
```

- [ ] **Step 3: Define required parameter ceilings and truncation rules**

```markdown
### Ceiling Rules

- log tail lines: max `200`
- log lookback duration: max `15m`
- Prometheus range window: max `30m`
- tool timeout default: `10s`
- tool retry ceiling default: `2`
- raw output characters before truncation: max `4000`

### Truncation Rules

- preserve first error line
- preserve line count summary
- preserve tool metadata summary
- never return unbounded raw payload
```

- [ ] **Step 4: Define a concrete minimum tool catalog for foundation v1**

```markdown
### Deliverables

- `describe_cloudwatch_alarm`
- `query_cloudwatch_metric`
- `describe_rds`
- `get_pod_status`
- `get_pod_events`
- `get_pod_logs`
- `describe_node`
- `query_prometheus`
```

- [ ] **Step 5: Verify mandatory enforcement sections and tool catalog exist**

Run: `rg -n "input schema validation|scope validation|AWS Wrapper Base|Kubernetes Wrapper Base|Prometheus Wrapper Base|describe_cloudwatch_alarm|query_prometheus" docs/platform-foundation/tool-layer.md`
Expected: 7 matches

- [ ] **Step 6: Commit**

```bash
git add docs/platform-foundation/tool-layer.md
git commit -m "docs: define platform foundation tool enforcement layer"
```

### Task 5: Define Security Boundary and Non-Production Write Boundary

**Files:**
- Modify: `docs/platform-foundation/security.md`
- Reference: `backlog/openclaw-security-boundary.md`
- Reference: `docs/platform-foundation/runtime.md`
- Reference: `docs/platform-foundation/tool-layer.md`
- Test: `docs/platform-foundation/security.md`

- [ ] **Step 1: Define runtime security baseline**

```markdown
## Decisions

### Kubernetes Runtime Baseline

- dedicated namespace
- dedicated service account
- `runAsNonRoot: true`
- `allowPrivilegeEscalation: false`
- `readOnlyRootFilesystem: true`
- `seccompProfile: RuntimeDefault`
- drop all Linux capabilities
- explicit CPU / memory requests and limits
```

- [ ] **Step 2: Define AWS and Kubernetes read-only boundaries**

```markdown
### AWS Baseline

- dedicated IRSA role
- no shared role with other workloads
- allow only `Get*` and `Describe*` families required by approved tools
- deny `Put*`, `Modify*`, `Delete*`, `Update*`, `Start*`, `Stop*`

### Kubernetes RBAC Baseline

- allow `get/list/watch` on `pods`, `pods/log`, `events`, `deployments`, `replicasets`, `nodes`
- deny `create/update/patch/delete`
- deny `exec`
- deny `port-forward`
- deny `secrets`
```

- [ ] **Step 3: Define network and secret handling**

```markdown
### Network Policy Baseline

Allow egress only to:

- Slack API
- LLM API endpoint
- Prometheus endpoint
- kube-apiserver
- AWS API endpoint

Default deny all other egress.

### Secret Handling

- use `ExternalSecrets`
- never place static credentials in pod spec
- redact API keys, bearer tokens, passwords, authorization headers, session tokens before reply
```

- [ ] **Step 4: Define the non-production write boundary explicitly**

```markdown
### Non-Production Write Boundary

- allowed only when `mode=non_prod_write`
- allowed environments: `staging`, `test`
- requires separate service account and separate IAM / RBAC policy set
- requires explicit approval marker in request contract
- every write action must emit audit event with actor, target, approval ref, and result
- write tool catalog must be separate from investigation tool catalog
```

- [ ] **Step 5: Verify security document includes runtime, IAM, RBAC, network, and write boundary sections**

Run: `rg -n "Kubernetes Runtime Baseline|AWS Baseline|Kubernetes RBAC Baseline|Network Policy Baseline|Non-Production Write Boundary" docs/platform-foundation/security.md`
Expected: 5 matches

- [ ] **Step 6: Commit**

```bash
git add docs/platform-foundation/security.md
git commit -m "docs: define platform foundation security boundary"
```

### Task 6: Define Observability and Rollout Controls

**Files:**
- Modify: `docs/platform-foundation/observability.md`
- Modify: `docs/platform-foundation/rollout.md`
- Reference: `docs/platform-foundation/contracts.md`
- Reference: `docs/platform-foundation/runtime.md`
- Reference: `docs/platform-foundation/security.md`
- Test: `docs/platform-foundation/observability.md`
- Test: `docs/platform-foundation/rollout.md`

- [ ] **Step 1: Define observability objectives, metrics, and failure taxonomy**

```markdown
## Objective

Make every run measurable for success, latency, policy denial, cost, redaction, and fallback behavior before any production rollout.

## Deliverables

- `openclaw_runs_total{source_product,result_state}`
- `openclaw_failures_total{source_product,error_reason}`
- `tool_calls_total{tool_name,result}`
- `tool_call_duration_seconds{tool_name}`
- `openclaw_tokens_total{source_product,model}`
- `redaction_hits_total{pattern_type}`
- `policy_denied_total{source_product,reason}`

## Failure Taxonomy

- `validation_failed`
- `policy_denied`
- `tool_timeout`
- `budget_exceeded`
- `redaction_failed`
- `slack_reply_failed`
```

- [ ] **Step 2: Define the audit log pipeline and retention posture**

```markdown
## Decisions

### Audit Pipeline

1. runtime emits structured audit event
2. audit event is redacted before persistence
3. large raw outputs are replaced by summary or hash
4. audit sink stores request metadata, tool summary, duration, result, error reason

### Retention Notes

- retain audit metadata longer than raw evidence
- do not persist secrets
- do not persist unbounded raw logs
```

- [ ] **Step 3: Define rollout stages and exit criteria**

```markdown
## Deliverables

### Local Fixtures

- sample ingress payloads for `alert_auto_investigator`
- sample ingress payloads for `self_service_ops_copilot`
- sample tool outputs for success, timeout, deny, and redaction cases

### Staging Dry-Run

- verify contracts parse cleanly
- verify policy denial is deterministic
- verify audit and metrics are emitted

### Shadow Mode

- run production-shaped requests without posting to the main thread
- measure parser success rate
- measure investigation success rate
- measure P95 latency
- measure token / cost
- run human sampling review

### Production Exit Criteria

- parser success rate meets target
- investigation success rate meets target
- P95 latency within budget
- policy deny behavior matches expectation
- redaction false negative count is zero in sample review
```

- [ ] **Step 4: Define the production rollout checklist**

```markdown
## Exit Criteria

- contracts frozen for v1
- runtime fallback path tested
- minimum tool catalog audited
- IRSA / RBAC / NetworkPolicy reviewed
- dashboards created
- shadow mode reviewed by platform owner
- rollback path documented
```

- [ ] **Step 5: Verify observability and rollout files contain metrics, taxonomy, and exit criteria**

Run: `rg -n "openclaw_runs_total|Failure Taxonomy|Audit Pipeline" docs/platform-foundation/observability.md && rg -n "Shadow Mode|Production Exit Criteria|rollback path documented" docs/platform-foundation/rollout.md`
Expected: first command returns 3 matches, second command returns 3 matches

- [ ] **Step 6: Commit**

```bash
git add docs/platform-foundation/observability.md docs/platform-foundation/rollout.md
git commit -m "docs: define platform foundation observability and rollout"
```

### Task 7: Align Backlog to Execution Tracks and Freeze DoD

**Files:**
- Modify: `backlog/platform-foundation-backlog.md`
- Modify: `docs/platform-foundation/README.md`
- Test: `backlog/platform-foundation-backlog.md`

- [ ] **Step 1: Rewrite the backlog phases so they point to execution tracks and document owners**

```markdown
## 執行軌道

| Track | 對應文件 | 主要依賴 | 完成定義 |
|---|---|---|---|
| Contracts | `docs/platform-foundation/contracts.md` | roadmap, security boundary | required schema 與 deny rule 固化 |
| Runtime | `docs/platform-foundation/runtime.md` | contracts | request / budget / fallback 固化 |
| Tool Layer | `docs/platform-foundation/tool-layer.md` | contracts, runtime | wrapper contract 與 minimum catalog 固化 |
| Security | `docs/platform-foundation/security.md` | runtime, tool layer | runtime / IAM / RBAC / network boundary 固化 |
| Observability | `docs/platform-foundation/observability.md` | contracts, runtime, security | metrics / audit / failure taxonomy 固化 |
| Rollout | `docs/platform-foundation/rollout.md` | all previous tracks | shadow mode 與 exit criteria 固化 |
```

- [ ] **Step 2: Replace generic acceptance bullets with measurable DoD**

```markdown
## 驗收標準

- 共用 contracts 已定義 required fields、deny behavior、owner
- runtime 已定義 request schema、budget、state machine、fallback
- minimum tool catalog 已定義 validation、scope、timeout、truncation、redaction、audit 順序
- production read-only boundary 已映射到 IRSA、RBAC、NetworkPolicy
- observability 已定義 metrics、failure taxonomy、audit retention rule
- rollout 已定義 local fixture、staging dry-run、shadow mode、production exit criteria
```

- [ ] **Step 3: Add implementation order and explicit handoff note**

```markdown
## 後續實作交接

本 repo 完成文件凍結後，`OpenClaw` 程式碼 repo 與 infra repo 需依文件順序實作，不得跳過 `contracts` 與 `security` 直接進入 product feature implementation。
```

- [ ] **Step 4: Verify the backlog now references all six tracks and measurable DoD**

Run: `rg -n "Contracts|Runtime|Tool Layer|Security|Observability|Rollout|驗收標準" backlog/platform-foundation-backlog.md`
Expected: 7 matches

- [ ] **Step 5: Commit**

```bash
git add backlog/platform-foundation-backlog.md docs/platform-foundation/README.md
git commit -m "docs: align platform foundation backlog with execution tracks"
```

## Self-Review

- **Spec coverage:** 本 plan 對應 `platform-foundation-backlog` 的共用契約、runtime、tool layer、security controls、observability、rollout 六個 phase；`NormalizedAlertEvent v1` 只作為 reference，不被誤納入 foundation implementation scope。
- **Placeholder scan:** 本 plan 沒有留空白佔位或模糊描述；每個 task 都附固定內容、驗證指令與 commit 點。
- **Type consistency:** 所有文件都沿用 `environment`、`account_allowlist`、`region_allowlist`、`request_id`、`result_state`、`max_tool_calls` 等同一組命名，避免後續 contracts 與 runtime 用語漂移。
