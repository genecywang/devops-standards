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

## Phase 0：共用契約

- [ ] 定義共用 config model
- [ ] 定義 environment / account / region scoping model
- [ ] 定義 Slack ingress model
- [ ] 定義共用 response envelope
- [ ] 定義 audit schema
- [ ] 定義 metrics schema

## Phase 1：OpenClaw Runtime

- [ ] 建立 `openclaw_runner`
- [ ] 定義 investigation / execution request schema
- [ ] 定義 execution budget model
- [ ] 定義 tool registration 介面
- [ ] 定義 retry / timeout / cancellation 行為
- [ ] 定義 fallback mode

## Phase 2：Tool Layer

- [ ] 建立 AWS tool wrapper base
- [ ] 建立 Kubernetes tool wrapper base
- [ ] 建立 Prometheus tool wrapper base
- [ ] 所有 tool 強制 input validation
- [ ] 所有 tool 強制 scope validation
- [ ] 所有 tool 強制 timeout / truncation
- [ ] 所有 tool 強制 audit logging
- [ ] 所有 tool 強制 redaction pass

## Phase 3：Security Controls

- [ ] 專屬 namespace / service account
- [ ] IRSA readonly role
- [ ] Kubernetes readonly RBAC
- [ ] NetworkPolicy default deny
- [ ] ExternalSecrets integration
- [ ] final output redaction policy
- [ ] non-production write action boundary 設計

## Phase 4：Observability

- [ ] `tool_calls_total`
- [ ] `tool_call_duration_seconds`
- [ ] `openclaw_runs_total`
- [ ] `openclaw_failures_total`
- [ ] `openclaw_tokens_total`
- [ ] `redaction_hits_total`
- [ ] `policy_denied_total`
- [ ] audit log pipeline

## Phase 5：Rollout

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

- 共用 tool layer 可同時支援 alert 與 self-service
- 所有 tool 均可審計
- read-only 邊界在 production 可強制執行
- fallback、timeout、redaction 行為可預測
