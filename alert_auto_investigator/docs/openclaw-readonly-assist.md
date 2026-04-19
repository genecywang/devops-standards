# Alert Auto Investigator — OpenClaw Read-Only Assist Contract

This document defines the intended boundary for Phase 2: OpenClaw as a
**read-only assist layer** on top of deterministic investigation results.

The goal is to gain explanatory and triage value from AI without weakening the
current tool-backed investigation system.

---

## Purpose

OpenClaw read-only assist exists to help humans interpret investigation output.

It may be used to:

- explain the current state in simpler terms
- suggest likely next steps
- aggregate repeated or grouped investigation results
- provide a lightweight operator-facing assessment

It does **not** replace deterministic investigation.

---

## Non-Goals

OpenClaw read-only assist must not:

- parse raw Slack alerts
- decide environment ownership
- bypass cooldown or rate-limit policy
- choose the primary investigation tool
- override support matrix behavior
- replace deterministic Slack investigation replies
- execute write actions
- generate arbitrary shell or `kubectl` commands for execution

If a proposal needs any of the above, it is outside this phase.

---

## Placement In The Current Flow

The intended sequence is:

1. Slack alert ingress
2. normalization into `NormalizedAlertEvent`
3. deterministic control decision
4. deterministic investigation dispatch
5. deterministic investigation reply posted to Slack
6. optional OpenClaw read-only assist consumes the investigation result
7. optional second Slack reply or side-channel output

This means:

- deterministic investigation remains the source of truth
- OpenClaw assist is downstream-only
- assist failure must never block the main investigation reply

---

## Stable Input Contract

The assist layer should consume already-normalized, already-investigated data.

Recommended input envelope:

```json
{
  "alert": {
    "source": "alertmanager",
    "alert_name": "KubernetesJobFailed",
    "alert_key": "alertmanager:H2S-EKS-DEV-STG-EAST-2:monitoring:KubernetesJobFailed:cronjob-iam-user-keyscan-manual-86x",
    "environment": "dev-tw",
    "cluster": "H2S-EKS-DEV-STG-EAST-2",
    "namespace": "monitoring",
    "resource_type": "job",
    "resource_name": "cronjob-iam-user-keyscan-manual-86x",
    "summary": "Kubernetes Job failed (instance 172.16.59.212:8080)"
  },
  "investigation": {
    "result_state": "success",
    "check": "get_job_status",
    "summary": "job cronjob-iam-user-keyscan-manual-86x failed: active=0, succeeded=0, failed=3, reason=BackoffLimitExceeded, message=Job has reached the specified backoff limit",
    "metadata": {
      "health_state": "failed",
      "attention_required": true,
      "resource_exists": true,
      "primary_reason": "BackoffLimitExceeded"
    }
  },
  "context": {
    "channel": "C03GC29TX8C",
    "thread_ts": "1776528303.221129"
  }
}
```

Required input properties:

- normalized alert identity
- deterministic investigation summary
- stable investigation metadata contract

Optional input properties:

- truncated evidence
- grouped sibling investigation results from the same thread
- channel / thread identifiers if assist output will be posted back

The assist layer should prefer metadata over reparsing natural-language summary.

---

## Stable Output Contract

The assist layer should return a bounded, structured payload.

Recommended output envelope:

```json
{
  "operator_assessment": "This is a terminal Job failure rather than a transient slow run.",
  "next_steps": [
    "Check the failed Job pod logs",
    "Review recent CronJob spec or dependency changes",
    "Confirm whether BackoffLimitExceeded is expected for this manual run"
  ],
  "confidence": "medium"
}
```

Required output properties:

- `operator_assessment`
- `next_steps`
- `confidence`

Recommended constraints:

- `operator_assessment` should be short and grounded in supplied metadata
- `next_steps` should be flat, concrete, and non-destructive
- `confidence` should be a small bounded enum such as:
  - `low`
  - `medium`
  - `high`

The assist layer should not emit executable commands as authoritative actions.

---

## Rollout Modes

OpenClaw read-only assist should be introduced in stages.

### 1. Shadow Mode

Behavior:

- OpenClaw consumes investigation results
- output is logged or stored only
- no Slack reply is posted

Use this mode to validate:

- usefulness
- noise level
- hallucination rate
- formatting quality

### 2. Opt-In Assist Mode

Behavior:

- enabled only for selected channels, environments, or alert shapes
- OpenClaw output is posted as a second Slack reply in the same thread

Use this mode to validate:

- whether humans actually find the assist useful
- whether it creates reply clutter

### 3. Policy-Aware Assist Mode

Behavior:

- assist is only invoked when investigation outcome suggests value

Recommended gating examples:

- `attention_required = true`
- `health_state in {"degraded", "failed"}`
- grouped multi-alert thread
- mismatch between upstream alert wording and current investigation outcome

---

## Prompting And Grounding Rules

The assist layer should be grounded only in:

- normalized alert fields
- deterministic investigation summary
- deterministic metadata
- optionally truncated evidence

It should not infer hidden context such as:

- business impact severity beyond supplied inputs
- whether to page or escalate unless explicitly modeled
- whether a write action should be executed

If evidence is missing, the assist output should say so rather than inventing detail.

---

## Slack Output Policy

If assist output is posted back to Slack, it should remain clearly secondary to
the deterministic investigation reply.

Recommended pattern:

- first reply: deterministic investigation result
- second reply: `AI Assist` or equivalent label

The assist reply should be concise and visibly distinct from the primary
investigation reply.

---

## Failure Policy

Assist-layer failure must be fail-open for the main system.

Required behavior:

- main investigation reply still posts normally
- assist timeout or model failure only suppresses the assist reply
- assist failure is logged with enough context for later review

No assist error should poison cooldown or make a successful investigation appear failed.

---

## Out Of Scope For This Phase

The following belong to later phases or separate systems:

- AI-driven tool routing
- AI-driven policy decisions
- AI-generated remediation commands
- autonomous rollout restarts
- production write actions
- replacing deterministic Slack formatter with freeform generation

---

## Exit Criteria Before Implementation

Before this phase starts, the following should already be true:

- investigation metadata contract is trusted
- investigation summaries are useful on real alerts
- company-specific assumptions are documented
- future action plane remains explicitly out of scope

If these are not true, Phase 1 work should continue instead.
