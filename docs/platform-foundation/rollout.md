# Rollout

## Objective

Define rollout controls that let platform owners validate contracts, shadow requests, and production readiness before any live exposure.

## In Scope

- local fixtures
- staging dry-run
- shadow mode
- production exit criteria
- production rollout checklist

## Out of Scope

- product-specific rollout choreography
- runtime implementation details
- dashboard wiring
- alert routing configuration

## Inputs and Dependencies

- `docs/platform-foundation/contracts.md`
- `docs/platform-foundation/runtime.md`
- `docs/platform-foundation/security.md`

## Decisions

### Deliverables

#### Local Fixtures

- sample ingress payloads for `alert_auto_investigator`
- sample ingress payloads for `self_service_ops_copilot`
- sample tool outputs for success, timeout, deny, and redaction cases

#### Staging Dry-Run

- verify contracts parse cleanly
- verify policy denial is deterministic
- verify audit and metrics are emitted

#### Shadow Mode

- run production-shaped requests without posting to the main thread
- measure parser success rate
- measure investigation success rate
- measure P95 latency
- measure token / cost
- run human sampling review

#### Production Exit Criteria

- parser success rate meets target
- investigation success rate meets target
- P95 latency within budget
- policy deny behavior matches expectation
- redaction false negative count is zero in sample review

### Production Rollout Checklist

- contracts frozen for v1
- runtime fallback path tested
- minimum tool catalog audited
- IRSA / RBAC / NetworkPolicy reviewed
- dashboards created
- shadow mode reviewed by platform owner
- rollback path documented

### Rollout Controls

- shadow mode must not post to the main thread
- staging dry-run must prove deterministic policy denial before production exposure
- production rollout cannot proceed until the checklist and exit criteria are complete
- a revert or disable path must exist and be owned before cutover

## Validation Rules

- `rollout.md` must define local fixtures, staging dry-run, shadow mode, production exit criteria, and the production rollout checklist
- rollout criteria must stay aligned with `contracts.md`, `runtime.md`, and `security.md`
- the document must keep rollback, shadow mode, and redaction review language explicit
- production exposure must remain gated by checklist completion and exit criteria

## Deliverables

- Canonical rollout stages for platform foundation validation
- Production checklist and exit criteria for safe exposure

## Exit Criteria

- local fixtures, staging dry-run, shadow mode, and production exit criteria are explicitly documented
- the production checklist includes an explicit rollback path
- rollout controls are aligned with the shared platform foundation contract and security boundaries

## Open Questions

- None for this task; any per-product rollout sequencing belongs outside this document
