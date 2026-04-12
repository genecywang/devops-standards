# Runtime

## Objective

Define a deterministic runtime boundary for `openclaw_runner` so product teams integrate through stable request / response contracts instead of ad hoc agent execution.

Owner: Platform Foundation.

## In Scope

- `investigation_request`
- `execution_request`
- `execution_budget`
- tool registration contract
- retry / timeout / cancellation rules
- fallback behavior

## Out of Scope

- LLM prompt wording
- source-specific event normalization
- product-specific Slack thread UX

## Inputs and Dependencies

- `docs/platform-foundation/contracts.md`
- `backlog/openclaw-security-boundary.md`
- `docs/superpowers/plans/2026-04-13-platform-foundation-implementation-plan.md`

## Decisions

### Request Schemas and Execution Budget

The runtime accepts two request types with a shared deterministic envelope. The request envelope uses `budget` as the execution budget object, and the budget fields are canonical across both request types:

- `max_steps`
- `max_tool_calls`
- `max_duration_seconds`
- `max_output_tokens`

#### Investigation Request

```json
{
  "request_type": "investigation",
  "request_id": "req-123",
  "source_product": "alert_auto_investigator",
  "scope": {
    "environment": "prod-jp",
    "account_id": "123456789012",
    "region_code": "ap-northeast-1",
    "cluster": "prod-jp-main"
  },
  "input_ref": "normalized-alert-event:cloudwatch_alarm:...",
  "budget": {
    "max_steps": 6,
    "max_tool_calls": 8,
    "max_duration_seconds": 45,
    "max_output_tokens": 1200
  }
}
```

#### Execution Request

```json
{
  "request_type": "execution",
  "request_id": "req-456",
  "source_product": "self_service_ops_copilot",
  "scope": {
    "environment": "staging",
    "cluster": "staging-main",
    "namespace": "payments"
  },
  "requested_action": "rollout_restart",
  "approval_state": "approved",
  "budget": {
    "max_steps": 4,
    "max_tool_calls": 4,
    "max_duration_seconds": 30,
    "max_output_tokens": 800
  }
}
```

Request validation must fail closed when required fields are missing or when the request type does not match the allowed schema for the source product.

### Runtime State Machine

1. `received`
2. `validated`
3. `policy_checked`
4. `executing`
5. `redacting`
6. `completed`

The runtime state machine is deterministic and monotonic. A request must not skip states, and `request_id` must remain stable for the full lifecycle of the run.

Internal runtime states describe processing progress only. Canonical response outcomes are carried by `result_state` in the shared response envelope, and implementers must not infer outcome from the last internal state name.

Outcome mapping:

- `completed` with successful validation, policy checks, execution, and redaction -> `result_state=success`
- validation failure or policy failure before execution -> `result_state=denied`
- explicit cancellation at any point before the run completes -> `result_state=partial`
- deterministic stop due to budget limit without further tool work -> `result_state=fallback`
- unrecoverable runtime or final redaction failure -> `result_state=failed`

### Failure Rules

- validation failure -> `denied`
- policy failure -> `denied`
- budget exceeded -> `fallback`
- cancellation -> `partial`
- tool timeout after retry ceiling -> `partial`
- final redaction failure -> `failed`

Failure handling must preserve auditability. When a failure occurs, the runtime should stop advancing state as soon as the terminal condition is known and emit the canonical response envelope with the matching `request_id` and `result_state`.

### Cancellation Rules

Cancellation is triggered only by an explicit cancel signal for the same `request_id`, a parent workflow cancellation, or a runtime drain / shutdown signal before the run completes.

When cancellation is received:

- stop starting new tool calls immediately
- allow the current in-flight tool call to return or time out within its existing timeout ceiling if that is already in progress
- do not advance into any later state once the cancellation is observed
- preserve already collected evidence for redaction and response assembly if possible
- emit the canonical response envelope with `result_state=partial`

If cancellation arrives before any actionable execution begins, the runtime still emits `result_state=partial` with a short cancellation summary rather than inventing a separate response outcome.

### Tool Registration Contract

Each tool must declare:

- `tool_name`
- `supported_request_types`
- `scope_requirements`
- `input_schema_ref`
- `timeout_seconds`
- `retry_ceiling`
- `redaction_profile`
- `audit_param_fields`

Tool registration is declarative only. The runtime must not infer missing tool constraints, and unregistered tools must be treated as unavailable.

### Fallback Mode

- stop new tool execution
- summarize only from collected evidence
- mark response `result_state=fallback`
- emit `openclaw_failures_total{source_product,error_reason}` with `error_reason="budget_exceeded"` when caused by budget limit

Fallback mode is the terminal safety path for budget exhaustion and similar deterministic stop conditions. It preserves the collected evidence already available to the runtime, but it does not start new tool work.

## Validation Rules

- `runtime.md` must define the objective, scope boundaries, request schemas, runtime state machine, tool registration contract, and fallback mode
- request examples must include both `investigation` and `execution` flows
- the runtime must align with `request_id`, `result_state`, and the shared execution budget fields defined in `contracts.md`
- runtime behavior must stay deterministic and fail closed on validation, policy, budget, timeout, cancellation, and redaction errors
- the document must not define LLM prompt wording, source-specific normalization, or Slack UX details

## Deliverables

- One canonical runtime boundary document for `openclaw_runner`
- A stable contract between product teams and runtime execution

## Exit Criteria

- The runtime objective, owner, in scope, and out of scope are explicit
- The request examples and state machine are present
- Tool registration and fallback behavior are defined
- The runtime document stays aligned with shared contracts and security boundary guidance

## Open Questions

- None for this task; unresolved product-specific behavior belongs outside the runtime core document
