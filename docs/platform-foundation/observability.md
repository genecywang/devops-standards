# Observability

## Objective

Make every run measurable for success, latency, policy denial, cost, redaction, and fallback behavior before any production rollout.

## In Scope

- run outcome metrics
- tool call metrics
- token and cost visibility
- redaction and policy denial tracking
- audit event emission checks

## Out of Scope

- dashboard implementation details
- alert routing policy
- exporter backend selection
- product-specific workflow behavior

## Inputs and Dependencies

- `docs/platform-foundation/contracts.md`
- `docs/platform-foundation/runtime.md`
- `docs/platform-foundation/security.md`

## Decisions

### Metrics

- `openclaw_runs_total{source_product,result_state}`
- `openclaw_failures_total{source_product,error_reason}`
- `tool_calls_total{tool_name,result}`
- `tool_call_duration_seconds{tool_name}`
- `openclaw_tokens_total{source_product,model}`
- `redaction_hits_total{pattern_type}`
- `policy_denied_total{source_product,reason}`

Metric labels are canonical and must align with the shared contracts document. Consumers must not rename series or synthesize missing labels.

### Failure Taxonomy

- `validation_failed`
- `policy_denied`
- `tool_timeout`
- `budget_exceeded`
- `redaction_failed`
- `slack_reply_failed`

Each failure reason must map to a deterministic runtime or delivery outcome. If the runtime cannot classify the failure safely, it must fail closed rather than invent a new reason.

### Audit Pipeline

1. runtime emits structured audit event
2. audit event is redacted before persistence
3. large raw outputs are replaced by summary or hash
4. audit sink stores request metadata, tool summary, duration, result, error reason

### Retention Posture

- retain audit metadata longer than raw evidence
- do not persist secrets
- do not persist unbounded raw logs
- keep raw payload retention shorter than redacted audit retention where both are required

### Observability Boundaries

- metrics must reflect `result_state` from the shared response envelope
- redaction events must be counted before any persisted telemetry is emitted
- policy denial counts must be emitted even when execution never starts
- fallback behavior must be observable as a first-class run outcome

## Validation Rules

- `observability.md` must define the objective, metrics, failure taxonomy, audit pipeline, and retention posture
- metrics names must match the canonical series in `contracts.md`
- audit content must exclude secrets and unbounded raw logs
- every deliverable must be aligned with `result_state`, redaction, and policy denial terminology used elsewhere in the platform foundation docs

## Deliverables

- Canonical observability objectives for platform foundation runs
- Canonical metric series and failure taxonomy
- Audit pipeline and retention posture for redacted persistence

## Exit Criteria

- metrics series are explicit and aligned with `contracts.md`
- failure taxonomy is defined and mapped to measurable outcomes
- audit pipeline and retention rules are documented

## Open Questions

- None for this task; implementation details for exporters, dashboards, and alerting belong outside this document
