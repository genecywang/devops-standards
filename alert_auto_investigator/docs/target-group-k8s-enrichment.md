# Alert Auto Investigator — Target Group To Kubernetes Enrichment

This document defines a **future enrichment layer** for `target_group`
investigation results.

It exists to keep the current AWS investigation tools bounded while still
leaving room for higher-value correlation later.

The current `get_target_group_status` tool remains intentionally narrow:

- AWS read-only
- `DescribeTargetGroups`
- `DescribeTargetHealth`
- no Kubernetes dependency

This document describes what may be added **after** that bounded tool is
already stable in production.

---

## Goal

Add optional, fail-open context that helps operators understand whether a
`target_group` likely belongs to a Kubernetes workload.

The enrichment goal is **context**, not ownership proof and not routing.

Examples of useful enrichment:

- likely related namespace
- likely related Service
- sample matching Pod IPs
- whether the target group appears EKS / AWS Load Balancer Controller managed

Examples of non-goals:

- replacing AWS investigation output
- changing support matrix routing
- deciding action policy
- hard-failing investigation when correlation is unavailable

---

## Core Rule

`target_group -> k8s` correlation must be treated as **best-effort enrichment**.

It must never become:

- a required step for successful investigation
- a hidden prerequisite for Slack reply
- a source of speculative ownership claims

If enrichment cannot prove a strong link, the system should return only the AWS
summary and nothing more.

---

## Allowed Inputs

Future enrichment may use only bounded, explainable signals.

Preferred signals, in order:

1. AWS tags on the target group
2. target group name / ARN pattern
3. target health registered IPs when `target_type=ip`
4. Kubernetes endpoint / pod IP reverse lookup

Secondary signals may be used only as supporting evidence:

- VPC ID
- known controller naming conventions
- namespace / service hints embedded in names

Do not use weak heuristics as the only basis for a claim.

---

## Acceptable Evidence Levels

Enrichment should classify confidence explicitly.

### Strong Evidence

Acceptable to surface as a concrete relationship:

- AWS tag directly identifies Kubernetes namespace and Service
- target IP matches a live Pod IP, and that Pod is selected by a Service that is
  a plausible owner of the target group
- multiple signals agree:
  - controller-style target group naming
  - matching Service endpoints
  - matching target IPs

Allowed output:

- `related_namespace`
- `related_service`
- `sample_pods`
- `confidence=high`

### Medium Evidence

Useful, but should be framed as likely rather than certain:

- naming pattern strongly suggests a Service
- controller-generated target group name maps to one candidate Service
- only a subset of target IPs can be matched

Allowed output:

- `likely_namespace`
- `likely_service`
- `confidence=medium`

### Weak Evidence

Do not surface as workload ownership:

- VPC match only
- name similarity only
- one ambiguous IP match
- controller-managed guess with multiple candidate Services

Allowed output:

- nothing beyond AWS summary
- optionally an internal debug log

---

## Fail-Open Rules

The enrichment layer must fail open in all of these cases:

- no matching Kubernetes object found
- multiple plausible Services found
- target IPs belong to resources outside Kubernetes scope
- Kubernetes API read fails
- AWS tag set is missing or inconsistent

Fail-open behavior means:

- investigation result stays `success`
- original AWS summary stays intact
- metadata contract stays unchanged
- enrichment is silently omitted or logged at INFO / DEBUG

It must **not**:

- convert success into failure
- change `health_state`
- change `attention_required`
- overwrite `primary_reason`

---

## Recommended Output Shape

If enrichment is later added, it should be a separate optional structure, not a
rewrite of the base investigation result.

Recommended shape:

```text
RelatedK8sNamespace: prod
RelatedK8sService: h2-api
RelatedK8sPods: 2 sample pods matched
EnrichmentConfidence: high
```

Or in machine-readable form:

```python
{
    "k8s_enrichment": {
        "namespace": "prod",
        "service": "h2-api",
        "sample_pods": ["h2-api-abc", "h2-api-def"],
        "confidence": "high",
    }
}
```

This must remain optional.

Consumers must work correctly when `k8s_enrichment` is absent.

---

## Explicit Non-Goals

The first enrichment phase must **not** do any of the following:

- infer Deployment ownership directly
- traverse Ingress / listener / rule graphs
- reconstruct full ALB topology
- correlate CloudWatch metrics to Kubernetes metrics
- guess ownership when there are multiple candidate Services
- make remediation decisions

Those are separate future phases and should not be hidden inside target group
enrichment.

---

## Suggested Rollout Order

1. document evidence rules first
2. implement shadow-only enrichment logs
3. verify real target groups in one non-prod environment
4. surface enrichment only when confidence is medium or high
5. keep low-confidence matches out of Slack reply

---

## Practical Decision

For now:

- keep `get_target_group_status` purely AWS-scoped
- do not block on Kubernetes correlation
- treat `target_group -> k8s` linkage as a future enrichment layer
- require strong evidence before surfacing any Kubernetes relationship
