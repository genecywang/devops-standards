# Alert Auto Investigator — Alert Key Strategy

This document defines how `alert_key` is built today and what role it plays in
the system.

`alert_key` is not a display field. It is part of the control contract.

It is used for:

- cooldown / dedupe
- investigation history tracking
- log correlation
- stable identity across parser, control, and investigation stages

---

## Design Rules

An `alert_key` should be:

- deterministic for the same source event identity
- built at normalization time, not later in the pipeline
- source-aware
- specific enough for cooldown to be meaningful

An `alert_key` should not:

- depend on Slack thread timestamps
- depend on reply formatting
- be rebuilt in handler or dispatcher logic

---

## Alertmanager Strategy

Alertmanager keys are built from normalized structured alert fields.

Base shape:

```text
alertmanager:{cluster}:{alert_name}:{resource_name}
```

Namespace-scoped shape:

```text
alertmanager:{cluster}:{namespace}:{alert_name}:{resource_name}
```

The namespace-scoped form is used for resource types in
`NAMESPACE_SCOPED_RESOURCE_TYPES`.

Current examples:

```text
alertmanager:H2S-EKS-DEV-STG-EAST-2:monitoring:KubernetesJobFailed:cronjob-iam-user-keyscan-manual-86x
alertmanager:H2S-EKS-DEV-STG-EAST-2:dev:KubernetesCronjobIdle:nightly-backfill
alertmanager:H2S-EKS-DEV-STG-EAST-2:prod:KubernetesContainerOomKiller:prod-h2-server-go-567589445c-n8b9s
```

Why namespace is included for some resource types:

- `job`, `cronjob`, `pod`, and other namespace-scoped targets may reuse the same resource name across namespaces
- cooldown should not collapse unrelated alerts from different namespaces

Why namespace is omitted for cluster-scoped or non-namespaced targets:

- namespace would add noise without increasing identity quality

---

## CloudWatch Strategy

CloudWatch keys are built from machine-readable alarm fields.

Shape:

```text
cloudwatch_alarm:{account_id}:{region_code}:{alarm_name}
```

Current example:

```text
cloudwatch_alarm:416885395773:ap-northeast-1:p-rds-shuriken_Blocked_Transactions
```

Why resource name is not included today:

- current CloudWatch identity is alarm-centric, not resource-centric
- the machine-readable block already exposes `resource_type` / `resource_name`, but alarm identity is still keyed on alarm source fields

This is acceptable for the current parse-only / notify-only AWS posture.

---

## What Must Stay Stable

The following contract should remain stable even if implementation details move:

- every normalized alert must either have a deterministic `alert_key` or be skipped
- key composition belongs to source-specific normalization / parser logic
- downstream control logic treats `alert_key` as opaque identity, not as a field to reinterpret

---

## What May Change Later

The following are valid future changes, but must be explicit:

- introducing new source-specific key strategies
- expanding namespace-scoped resource-type coverage
- tightening CloudWatch key identity if AWS investigation becomes resource-aware

Any such change should be accompanied by:

- golden replay updates
- control behavior review
- cooldown / dedupe impact review
