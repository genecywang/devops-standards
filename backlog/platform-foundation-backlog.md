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
| Contracts | `docs/platform-foundation/contracts.md` | roadmap, security boundary | required schema 與 deny rule 固化 |
| Runtime | `docs/platform-foundation/runtime.md` | contracts | request / budget / fallback 固化 |
| Tool Layer | `docs/platform-foundation/tool-layer.md` | contracts, runtime | wrapper contract 與 minimum catalog 固化 |
| Security | `docs/platform-foundation/security.md` | runtime, tool layer | runtime / IAM / RBAC / network boundary 固化 |
| Observability | `docs/platform-foundation/observability.md` | contracts, runtime, security | metrics / audit / failure taxonomy 固化 |
| Rollout | `docs/platform-foundation/rollout.md` | all previous tracks | shadow mode 與 exit criteria 固化 |

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

- 共用 contracts 已定義 required fields、deny behavior、owner
- runtime 已定義 request schema、budget、state machine、fallback
- minimum tool catalog 已定義 validation、scope、timeout、truncation、redaction、audit 順序
- production read-only boundary 已映射到 IRSA、RBAC、NetworkPolicy
- observability 已定義 metrics、failure taxonomy、audit retention rule
- rollout 已定義 local fixture、staging dry-run、shadow mode、production exit criteria

## 後續實作交接

本 repo 完成文件凍結後，`OpenClaw` 程式碼 repo 與 infra repo 需依文件順序實作，不得跳過 `contracts` 與 `security` 直接進入 product feature implementation。
