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
