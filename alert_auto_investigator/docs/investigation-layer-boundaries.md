# Alert Auto Investigator — Investigation Layer Boundaries

This document defines the responsibility boundary between:

- `alert_auto_investigator` as the deterministic incident gateway
- future OpenClaw as the exploratory investigation layer
- any later action plane

The goal is to stop scope drift.

This system should not become a half-agent, and OpenClaw should not take over
deterministic policy and ingress concerns.

---

## Why This Boundary Exists

The current system already provides value that a free-form agent should not
replace:

- structured alert ingestion
- deterministic control policy
- explicit support matrix
- bounded tool routing
- deterministic Slack reply formatting
- stable investigation metadata

At the same time, this system has an upper bound:

- it is not a root-cause engine
- it is not a free-form CLI investigator
- it is not a remediation agent

Without a written boundary, the implementation will drift in one of two bad
directions:

- the deterministic layer becomes an increasingly complex pseudo-agent
- OpenClaw is forced to re-solve ingress, policy, and normalization every time

Neither is acceptable.

---

## Layer Model

The intended model has three layers:

1. deterministic incident gateway
2. exploratory read-only investigation
3. guarded action plane

These are separate concerns and should not be collapsed into one runtime.

---

## Layer 1 — Deterministic Incident Gateway

This is the role of `alert_auto_investigator`.

### Primary Responsibilities

- ingest Slack alerts from known sources
- normalize alerts into stable machine-readable structure
- apply ownership, cooldown, rate limit, and allow / deny policy
- route only supported resource types to bounded tools
- produce deterministic Slack replies
- emit stable metadata for later consumers

### Allowed Capabilities

This layer may perform:

- fixed parser logic
- fixed control decisions
- fixed tool dispatch
- bounded read-only correlation
- bounded status aggregation
- deterministic summary generation

### What Counts As Acceptable Correlation

Correlation remains in Layer 1 only when all of the following are true:

- the inputs are fixed and known in advance
- the query path is fixed and explainable
- the output shape is fixed
- the result can be omitted without breaking the investigation
- confidence can be expressed deterministically
- the logic does not require free-form search

Examples that fit Layer 1:

- `job` alert -> fixed `get_job_status`
- `target_group` alert -> best-effort `namespace` / `service` enrichment from
  bounded evidence
- `pod` alert -> latest event summary from Kubernetes events

### Not Allowed In Layer 1

This layer must not perform:

- root cause inference
- multi-step adaptive search
- free-form CLI exploration
- remediation suggestion
- speculative ownership claims
- alert-specific narrative reasoning
- autonomous decision-making about what other systems to inspect next

Examples that do **not** fit Layer 1:

- "the health check is probably failing because readiness is misconfigured"
- "this RDS alarm is likely caused by query backlog and autovacuum lag"
- "I could not find enough evidence, so I also searched logs and metrics"

### Output Standard

Layer 1 output should answer:

- what resource was checked
- what tool was used
- what the current observable state is
- whether attention is required
- what the primary deterministic reason is

It should not try to answer:

- why the incident happened in a human causal sense
- what the operator should do next, beyond bounded fixed wording

---

## Layer 2 — OpenClaw Exploratory Investigation

This is a future layer, not the current bot.

### Primary Responsibilities

- consume normalized alert context
- consume deterministic investigation output
- gather more evidence when the baseline is insufficient
- explain likely interpretations
- suggest next steps for operators

### Why Layer 2 Exists

Many incidents cannot be understood from baseline status alone.

Examples:

- an RDS instance may be `available`, while the real problem is storage trend,
  workload shape, or configuration mismatch
- a target group may be unhealthy, while the useful next question is which
  workload it fronts and what changed
- a Kafka lag alert may require inspecting multiple systems before it becomes
  actionable

These are valid investigation problems, but they are not a good fit for
deterministic, fixed-path tooling.

### Allowed Capabilities

Layer 2 may perform:

- multi-step read-only evidence gathering
- dynamic tool selection within an approved read-only toolset
- cross-system evidence comparison
- operator-facing explanation
- next-step suggestion
- confidence reporting

### Constraints

Even in Layer 2:

- read-only first
- explicit tool allowlist
- explicit cluster / namespace / account scope
- failures must not block Layer 1 reply
- deterministic Layer 1 output remains the source of truth

### Output Standard

Layer 2 may add:

- `operator_assessment`
- `next_steps`
- `confidence`
- grouped interpretation across repeated or related alerts

Layer 2 must not replace:

- parser behavior
- support matrix
- control policy
- deterministic routing
- deterministic investigation reply

---

## Layer 3 — Guarded Action Plane

This is explicitly later than both Layer 1 and Layer 2.

Its purpose is not diagnosis. Its purpose is controlled state change.

### Preconditions

Do not start this layer until:

- Layer 1 output is trusted in operation
- Layer 2 output has proven useful in shadow or opt-in mode
- approval, audit, and rollback requirements are written down

### First Acceptable Scope

- non-production only
- explicit approval required
- bounded actions only
- least-privilege execution identity

This layer must remain separate from both investigation layers.

---

## Baseline Truth Definition

`baseline truth` does **not** mean full incident understanding.

It means:

- the minimum trusted facts that can be obtained
- through fixed, bounded, read-only access
- with stable output shape
- and predictable operational cost

Baseline truth is intentionally incomplete.

That is acceptable.

Examples of acceptable baseline truth:

- `job` exists and failed with `BackoffLimitExceeded`
- `target_group` has `3` unhealthy targets
- `load_balancer` exists and is `active`
- `rds_instance` exists and is `available`

Examples of things that are **not** baseline truth:

- why backlog suddenly increased
- whether a deployment introduced the regression
- whether a readiness probe, app bug, or network policy is the most likely cause

Those belong to exploratory investigation.

---

## Why Not Let OpenClaw Do Everything

A constrained OpenClaw agent can eventually be more powerful than the current
deterministic gateway.

That still does not make Layer 1 unnecessary.

Layer 1 exists because it provides:

- stable ingestion
- stable policy enforcement
- stable contracts
- low-cost baseline facts
- predictable behavior
- easy replay and audit

OpenClaw should build on top of those guarantees, not reimplement them from raw
Slack text each time.

The architectural principle is:

- Layer 1 provides facts
- Layer 2 provides meaning
- Layer 3 performs actions

---

## Decision Rules

When deciding where new work belongs, use these rules.

A capability belongs in Layer 1 only if:

- it can be expressed as fixed inputs + fixed query path + fixed output
- it is explainable without narrative reasoning
- it can fail open safely
- it improves the baseline fact surface

A capability belongs in Layer 2 if:

- it requires dynamic search
- it requires choosing among multiple next steps
- it depends on combining evidence opportunistically
- it is primarily about interpretation or recommendation

A capability belongs in Layer 3 if:

- it changes live state
- it triggers rollouts, restarts, scaling, or mutations

---

## Practical Guidance For Current Work

Given the current product stage:

- continue strengthening Layer 1 only where the result is deterministic and
  bounded
- allow identity and topology correlation in Layer 1 when evidence is strong
- do not push causal diagnosis into Layer 1
- use Layer 1 output as the contract for future OpenClaw assist

This means, for example:

- `target_group -> likely Service` can be a valid Layer 1 enrichment
- `target_group health failure root cause analysis` is a Layer 2 concern
- `RDS status summary` is Layer 1
- `RDS alarm cause interpretation` is Layer 2

That boundary should remain explicit in both code and documentation.
