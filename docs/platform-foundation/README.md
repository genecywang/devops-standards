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

1. Contracts - `docs/platform-foundation/contracts.md`
2. Runtime - `docs/platform-foundation/runtime.md`
3. Tool Layer - `docs/platform-foundation/tool-layer.md`
4. Security - `docs/platform-foundation/security.md`
5. Observability - `docs/platform-foundation/observability.md`
6. Rollout - `docs/platform-foundation/rollout.md`

## Dependency Order

`contracts` -> `runtime` -> `tool-layer` -> `security` -> `observability` -> `rollout`
