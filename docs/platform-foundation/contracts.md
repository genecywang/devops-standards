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
- Consumer-specific runtime and tool execution docs that will implement these contracts later

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

Owner: Platform Foundation. Retention: follow the destination sink policy; the contract only requires that the audit record is durable enough for post-run review and incident forensics.

### Metrics Schema

- `openclaw_runs_total{source_product,result_state}`
- `openclaw_failures_total{source_product,error_reason}`
- `tool_calls_total{tool_name,result}`
- `tool_call_duration_seconds{tool_name}`
- `openclaw_tokens_total{source_product,model}`
- `redaction_hits_total{pattern_type}`
- `policy_denied_total{source_product,reason}`

Owner: Platform Foundation. Retention: metrics retention follows the observability backend defaults and should support trend analysis across rollout phases.

## Validation Rules

- `contracts.md` must contain all fixed headings required by the platform foundation plan
- config model must include allowlists and execution budget fields
- scope deny rules must fail closed on missing `environment`, unauthorized account, unauthorized region, and write intent in `read_only` mode
- ingress and response envelopes must both carry `request_id`
- audit schema must include `tool_names`, `tool_param_summary`, `duration_ms`, and `policy_denied`
- metrics schema must include run, failure, tool call, token, redaction, and policy denial counters / histograms

## Deliverables

- One canonical shared contract document for `Platform Foundation`
- A clear boundary between shared contracts and later runtime / tool implementation docs

## Exit Criteria

- All contract sections are populated
- The shared config, ingress, response, audit, and metrics contracts are explicit and internally consistent
- No `NormalizedAlertEvent` source mapping or product-specific Slack copywriting is defined here

## Open Questions

- None for this task; remaining implementation detail belongs to runtime and product-specific documents
