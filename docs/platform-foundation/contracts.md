# Contracts

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

## Inputs and Dependencies

- `backlog/platform-foundation-backlog.md`
- `backlog/normalized-alert-event-v1.md`
- `backlog/openclaw-security-boundary.md`

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

Owner: Platform Foundation.

Validation / deny behavior:

- missing required fields must deny contract acceptance before runtime or tool execution starts
- `mode=read_only` must deny any write intent
- allowlist fields must be treated as hard gates, not hints

### Scope Deny Rules

- missing `environment` -> deny ownership-sensitive execution
- target account not in `account_allowlist` -> deny
- target region not in `region_allowlist` -> deny
- `mode=read_only` with write intent -> deny

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

Owner: Platform Foundation.

Validation / deny behavior:

- any missing required ingress field must deny request processing before execution starts
- invalid `source_product`, `actor_type`, or `payload_type` values must fail closed
- `request_id` must be stable for the full lifecycle of the request

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

Owner: Platform Foundation.

Validation / deny behavior:

- any missing required response field must prevent emission of a canonical response envelope
- `result_state` values outside the enumerated set must be rejected
- `request_id` must match the ingress request id for the same run

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

Owner: Platform Foundation.

Validation / deny behavior:

- any missing required audit field must make the audit record invalid
- audit records must be emitted only after required fields are populated and redaction has been applied where needed
- `policy_denied` must be set explicitly for every record

### Metrics Schema

- `openclaw_runs_total{source_product,result_state}`
- `openclaw_failures_total{source_product,error_reason}`
- `tool_calls_total{tool_name,result}`
- `tool_call_duration_seconds{tool_name}`
- `openclaw_tokens_total{source_product,model}`
- `redaction_hits_total{pattern_type}`
- `policy_denied_total{source_product,reason}`

Owner: Platform Foundation.

Validation / deny behavior:

- metric names and label keys are canonical and must not be renamed by consumers
- missing required labels must drop the metric event rather than synthesize partial labels
- metrics definitions stay within contract scope; exporter/backend policy is out of scope

## Validation Rules

- `contracts.md` must contain all fixed headings required by the platform foundation plan
- config model must include `environment`, account / region allowlists, optional cluster / namespace allowlists, `mode`, and execution budget fields
- config validation must fail closed on missing required fields, unauthorized account, unauthorized region, and write intent in `read_only` mode
- ingress validation must fail closed when any required field is missing or has an invalid enumerated value
- response validation must fail closed when any required field is missing or `result_state` is outside the canonical set
- audit validation must fail closed when any required field is missing or when redaction has not been applied before emission
- metrics schema must include run, failure, tool call, token, redaction, and policy denial series with canonical names and labels
- shared contracts must not rely on runtime-specific fallbacks to compensate for missing required contract fields

## Deliverables

- One canonical shared contract document for `Platform Foundation`
- A clear boundary between shared contracts and later runtime / tool implementation docs

## Exit Criteria

- All contract sections are populated
- The shared config, ingress, response, audit, and metrics contracts are explicit and internally consistent
- No `NormalizedAlertEvent` source mapping or product-specific Slack copywriting is defined here

## Open Questions

- None for this task; remaining implementation detail belongs to runtime and product-specific documents
