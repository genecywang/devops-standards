# Alert Auto Investigator — Future Phases

This document captures the intended sequencing for future work. It exists to
prevent write-action scope from leaking into the current read-only
investigation system too early.

The current product remains:

- a structured-alert ingress
- a deterministic control pipeline
- a tool-backed investigation plane
- a deterministic Slack reply surface

It is **not** yet an autonomous remediation system.

---

## Phase Order

Future work should follow this order:

1. strengthen deterministic investigation coverage
2. add OpenClaw read-only assist on top of investigation output
3. only then consider a guarded non-prod action plane

This ordering is intentional:

- investigation output must be trusted before any reasoning layer consumes it
- reasoning output must prove useful before any write action is introduced
- write actions must remain the final step because they change cluster state

---

## Phase 1 — Investigation Maturity

Before any AI assist or write action is added, the investigation plane should
continue to mature in the current direction:

- expand support only where investigation value is clear
- keep `SUPPORT_MATRIX` explicit
- keep Slack replies deterministic
- keep metadata contract stable:
  - `health_state`
  - `attention_required`
  - `resource_exists`
  - `primary_reason`
- keep golden replay coverage current for real alert shapes

Success criteria:

- supported resource types have clear routing and clear skip behavior
- real alert replay confirms investigation summaries are operationally useful
- metadata is stable enough to be consumed by later layers without alert-specific parsing

---

## Phase 2 — OpenClaw Read-Only Assist

Once investigation output is stable, OpenClaw may be added as a **read-only
assist layer**.

OpenClaw's role in this phase is limited to:

- explaining the current investigation outcome
- suggesting likely next steps
- aggregating grouped or repeated investigation results
- helping humans interpret deterministic findings

OpenClaw must **not** take over:

- alert parsing
- control policy
- investigation routing
- final Slack investigation formatting
- direct cluster writes

Recommended input to OpenClaw:

- normalized alert fields
- deterministic investigation summary
- investigation metadata
- optionally truncated evidence

Recommended output from OpenClaw:

- `operator_assessment`
- `next_steps`
- `confidence`

Recommended rollout order:

1. shadow mode only
2. opt-in Slack second reply for selected channels or environments
3. policy-aware assist for selected actionable investigation outcomes

Success criteria:

- OpenClaw output is consistently useful and not noisy
- deterministic investigation remains the source of truth
- failures in the assist layer never block investigation reply

---

## Phase 3 — Guarded Non-Prod Action Plane

Write actions should only be considered after Phase 1 and Phase 2 have proven
useful in real operation.

The first acceptable scope is intentionally narrow:

- non-production environments only
- allowlisted namespaces only
- allowlisted clusters only
- supported target kinds only:
  - `deployment`
  - `statefulset`
- deterministic action types only
- human approval required

The first candidate action is:

- `rollout_restart_workload`

Resolved runtime behavior:

- if target kind is `deployment`, execute a deployment rollout restart
- if target kind is `statefulset`, execute a statefulset rollout restart
- if target kind is unsupported, deny action deterministically

This phase must remain separate from the investigation plane:

- investigation reads state
- action changes state

Minimum guardrails:

- feature flag / global kill switch
- explicit action allowlist
- explicit namespace and cluster allowlists
- production deny by policy
- deterministic action formatter
- audit log including actor, target, action, and result
- least-privilege RBAC for action service account

Not in scope for the first action phase:

- deleting pods directly
- arbitrary `kubectl` execution
- restarting Jobs or CronJobs
- scaling workloads
- patching workload specs
- production write actions
- AI-generated commands
- autonomous action without human approval

Success criteria:

- actions are policy-bounded and auditable
- action failure does not corrupt investigation flow
- rollout restart behavior is predictable in non-prod namespaces

---

## Decision Rules

When evaluating future proposals, use these rules:

- if it changes cluster state, it belongs after read-only assist
- if it weakens deterministic investigation, reject it
- if it requires AI to decide routing or policy, reject it
- if it can be expressed as a fixed enum plus fixed policy, it is a better candidate

---

## Short-Term Priority

The near-term focus should remain on Phase 1 work:

- continue tightening investigation support and coverage
- document company-specific assumptions explicitly
- keep the investigation metadata contract stable

Do not start action-plane implementation until:

- investigation output is trusted
- OpenClaw read-only assist shape is agreed
- action RBAC and audit requirements are written down
