# Platform Foundation Backlog

## 目標

建立 `OpenClaw` 驅動的 AI 平台共用底座，供以下兩條產品線共用：

- `Alert Auto-Investigator`
- `Self-Service Ops Copilot`

## 範圍

- Slack ingress / responder
- `OpenClaw` runner
- tool registry / tool wrapper
- IAM / RBAC / Network policy
- audit / metrics / redaction
- environment / scope control
- shared config 與 execution budget

## 執行軌道

| Track | 對應文件 | 主要依賴 | 完成定義 |
|---|---|---|---|
| Contracts | `docs/platform-foundation/contracts.md` | foundation 起始軌道，後續依賴順序以 `docs/platform-foundation/README.md` 為準 | required schema 與 deny rule 固化 |
| Runtime | `docs/platform-foundation/runtime.md` | `Contracts` | request / budget / fallback 固化 |
| Tool Layer | `docs/platform-foundation/tool-layer.md` | `Contracts -> Runtime` | wrapper contract 與 minimum catalog 固化 |
| Security | `docs/platform-foundation/security.md` | `Runtime -> Tool Layer` | runtime / IAM / RBAC / network boundary 固化 |
| Observability | `docs/platform-foundation/observability.md` | `Contracts -> Runtime -> Security` | metrics / audit / failure taxonomy 固化 |
| Rollout | `docs/platform-foundation/rollout.md` | `Contracts -> Runtime -> Tool Layer -> Security -> Observability` | shadow mode 與 exit criteria 固化 |

## Phase 0：共用契約

- [ ] 定義共用 config model
- [ ] 定義 environment / account / region scoping model
- [ ] 定義 Slack ingress model
- [ ] 定義共用 response envelope
- [ ] 定義 audit schema
- [ ] 定義 metrics schema

## Phase 1：OpenClaw 執行階段

- [ ] 建立 `openclaw_runner`
- [ ] 定義 investigation / execution request schema
- [ ] 定義 execution budget model
- [ ] 定義 tool registration 介面
- [ ] 定義 retry / timeout / cancellation 行為
- [ ] 定義 fallback mode

## Phase 2：工具層

- [ ] 建立 AWS tool wrapper base
- [ ] 建立 Kubernetes tool wrapper base
- [ ] 建立 Prometheus tool wrapper base
- [ ] 所有 tool 強制 input validation
- [ ] 所有 tool 強制 scope validation
- [ ] 所有 tool 強制 timeout / truncation
- [ ] 所有 tool 強制 audit logging
- [ ] 所有 tool 強制 redaction pass

## Phase 3：安全控制

- [ ] 專屬 namespace / service account
- [ ] IRSA readonly role
- [ ] Kubernetes readonly RBAC
- [ ] NetworkPolicy default deny
- [ ] ExternalSecrets integration
- [ ] final output redaction policy
- [ ] non-production write action boundary 設計

## Phase 4：可觀測性

- [ ] `tool_calls_total`
- [ ] `tool_call_duration_seconds`
- [ ] `openclaw_runs_total`
- [ ] `openclaw_failures_total`
- [ ] `openclaw_tokens_total`
- [ ] `redaction_hits_total`
- [ ] `policy_denied_total`
- [ ] audit log pipeline

## Phase 5：上線切換

- [ ] local fixtures
- [ ] staging dry-run
- [ ] shadow mode
- [ ] exit criteria
- [ ] production rollout checklist

## 實作文件對應

- `docs/platform-foundation/contracts.md`
- `docs/platform-foundation/runtime.md`
- `docs/platform-foundation/tool-layer.md`
- `docs/platform-foundation/security.md`
- `docs/platform-foundation/observability.md`
- `docs/platform-foundation/rollout.md`

## 驗收標準

- `docs/platform-foundation/contracts.md` 已明確列出 config、ingress、response、audit、metrics 的 required fields、owner、validation / deny behavior，且命名與其他 foundation 文件一致
- `docs/platform-foundation/runtime.md` 已明確列出 `investigation` / `execution` request schema、execution budget、runtime state machine、failure outcome mapping、fallback / cancellation 規則
- `docs/platform-foundation/tool-layer.md` 已明確列出 schema validation -> scope validation -> timeout budget allocation -> upstream call -> truncation -> redaction -> audit emission 的強制順序，並列出 minimum foundation v1 tool catalog
- `docs/platform-foundation/security.md` 已明確列出 production read-only baseline 與 non-production write overlay，並對齊 Kubernetes runtime baseline、IRSA、RBAC、NetworkPolicy、secret redaction boundary
- `docs/platform-foundation/observability.md` 已明確列出 canonical metrics、failure taxonomy、audit pipeline、retention posture，且 audit 欄位名與 shared contract 一致
- `docs/platform-foundation/rollout.md` 已明確列出 local fixtures、staging dry-run、shadow mode、production rollout checklist、production exit criteria，且 rollback path 為必備 gating item

## 後續實作交接

本 repo 完成文件凍結後，`OpenClaw` 程式碼 repo 與 infra repo 需先閱讀 `docs/platform-foundation/README.md` 的 execution tracks 與 dependency order，再依 `contracts -> runtime -> tool-layer -> security -> observability -> rollout` 的順序實作，不得跳過 `contracts` 與 `security` 直接進入 product feature implementation。
