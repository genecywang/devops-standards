# Rollout

## Objective

Define rollout controls that let platform owners validate contracts, shadow requests, and production readiness before any live exposure.

Owner: Platform Foundation.

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
- `docs/platform-foundation/normalized-alert-contract.md`
- `docs/platform-foundation/runtime.md`
- `docs/platform-foundation/security.md`
- `docs/platform-foundation/observability.md`

## Decisions

### Rollout Stages

#### Local Fixtures

- sample ingress payloads for representative investigation and execution requests
- sample tool outputs for success, timeout, deny, and redaction cases

#### Staging Dry-Run

- verify contracts parse cleanly
- verify policy denial is deterministic
- verify audit and metrics are emitted

#### Shadow Mode

- run production-shaped requests without posting to the main thread
- measure contract validation success rate
- measure run success rate
- measure P95 latency
- measure token / cost
- run human sampling review

#### Production Exit Criteria

- contract validation success rate meets the target approved by the platform owner before exposure
- run success rate meets the target approved by the platform owner before exposure
- P95 latency remains within the rollout budget approved for the environment
- policy deny behavior matches the expected fail-closed policy outcomes from staging and shadow review
- redaction false negative count is zero in the approved sample review set

### Production Rollout Checklist

Checklist items are required control actions that must be completed before production exposure. They are not the measurable outcome gates themselves.

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

- all production rollout checklist items are complete:
  `contracts frozen for v1`, `runtime fallback path tested`, `minimum tool catalog audited`, `IRSA / RBAC / NetworkPolicy reviewed`, `dashboards created`, `shadow mode reviewed by platform owner`, `rollback path documented`
- local fixtures, staging dry-run, shadow mode, and production exit criteria are explicitly documented
- production exit criteria use approved target and budget values owned by the platform owner for the current environment
- rollout controls are aligned with the shared platform foundation contract and security boundaries

## Open Questions

- None for this task; any per-product rollout sequencing belongs outside this document
