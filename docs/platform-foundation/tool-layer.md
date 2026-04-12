# Tool Layer

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

## In Scope

- wrapper contract for AWS, Kubernetes, and Prometheus tools
- mandatory enforcement order for tool execution
- parameter ceilings and output truncation rules
- minimum foundation v1 tool catalog

## Out of Scope

- IAM policy design
- Kubernetes RBAC design
- runtime state machine definition
- product-specific rollout or incident response behavior

## Inputs and Dependencies

- `docs/platform-foundation/contracts.md`
- `docs/platform-foundation/runtime.md`
- `backlog/openclaw-security-boundary.md`

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

### Deliverables

- `describe_cloudwatch_alarm`
- `query_cloudwatch_metric`
- `describe_rds`
- `get_pod_status`
- `get_pod_events`
- `get_pod_logs`
- `describe_node`
- `query_prometheus`

## Validation Rules

- `tool-layer.md` must contain the objective, validation rules, wrapper base decisions, ceiling rules, truncation rules, and deliverables sections
- schema gating and scope gating must be explicit enforcement steps in the required tool execution order
- provider wrapper bases must each be defined as mandatory base contracts
- the foundation v1 tool catalog must include the minimum AWS, Kubernetes, and Prometheus entries
- wrapper behavior must align with `contracts.md`, `runtime.md`, and the security boundary guidance on fail-closed, redaction, and auditability
- the document must not expand into IAM / RBAC policy implementation, runtime orchestration, or rollout procedures

## Deliverables

- One canonical tool wrapper contract for Platform Foundation
- A minimum foundation v1 catalog for AWS, Kubernetes, and Prometheus tools

## Exit Criteria

- The mandatory execution order is explicit
- Provider-specific wrapper bases are explicit
- Ceiling and truncation rules are explicit
- The foundation v1 tool catalog is explicit and aligned with the security boundary guidance

## Open Questions

- None for this task; remaining provider policy details belong in IAM / RBAC / runtime implementation documents
