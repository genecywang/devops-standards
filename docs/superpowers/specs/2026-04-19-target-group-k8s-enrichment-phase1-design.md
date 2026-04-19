# Target Group K8s Enrichment Phase 1 Design

## Goal

Add a **bounded, deterministic, fail-open** enrichment step for
`target_group` investigations so Slack replies can optionally include:

- `RelatedK8sNamespace`
- `RelatedK8sService`

This phase is intentionally narrow.

It exists to improve the operational value of AWS target group alarms without
turning `alert_auto_investigator` into a free-form reasoning agent.

---

## Why This Phase Exists

Current `target_group` investigation is AWS-only and can answer:

- whether the target group exists
- target health counts
- target type
- protocol / port

That is useful, but it often stops short of the operator's next question:

- which Kubernetes workload is this target group actually fronting?

Phase 1 does **not** try to answer why the target group is unhealthy.

It only tries to answer whether there is strong deterministic evidence that the
target group belongs to a specific Kubernetes `Service`.

---

## Scope

### In Scope

- only `resource_type=target_group`
- only best-effort enrichment after successful base investigation
- only `high confidence` enrichment is shown in Slack
- only Kubernetes `namespace` and `Service` identity are surfaced
- fail-open behavior when enrichment cannot prove a strong link

### Out Of Scope

- Deployment / StatefulSet ownership inference
- Ingress / listener / rule traversal
- health check failure root cause analysis
- medium-confidence or likely ownership output in Slack
- any change to primary metadata contract:
  - `health_state`
  - `attention_required`
  - `resource_exists`
  - `primary_reason`

---

## Boundary

This phase belongs to Layer 1 because the enrichment remains:

- bounded
- deterministic
- explainable
- optional
- fail-open

This phase must **not** become:

- a free-form search flow
- an adaptive multi-step investigation engine
- an ownership guesser
- a substitute for future OpenClaw exploratory investigation

---

## Proposed Flow

1. CloudWatch target group alarm is parsed and normalized.
2. Control pipeline decides the alert should be investigated.
3. Dispatcher runs `get_target_group_status`.
4. If the base investigation succeeds, run optional K8s enrichment.
5. If enrichment reaches `high confidence`, append fixed enrichment lines to
   the Slack reply.
6. If enrichment fails or remains below `high confidence`, return the original
   AWS investigation reply unchanged.

---

## Evidence Model

Phase 1 may use only strong, bounded evidence.

### Allowed Evidence Sources

1. AWS target group tags
2. target health registered IPs from `DescribeTargetHealth`
3. Kubernetes reverse lookup from Pod IP to Pod
4. Kubernetes `Service` selection / endpoint relationship

### Preferred Matching Order

The first implementation should prefer the strongest and simplest path:

1. extract registered target IPs from target group health
2. map target IPs to live Pods in allowed namespaces
3. identify candidate `Service` objects that plausibly own those Pods
4. require a single unambiguous `namespace/service` result

AWS tags may be used if they are stable and clearly identify Kubernetes
ownership, but they must not be the only basis unless they are explicit enough
to stand on their own.

### High Confidence Rule

Slack output is allowed only when all of the following are true:

- at least one target IP matches a live Pod IP
- matched Pods point to exactly one plausible `namespace/service`
- there is no conflicting second candidate
- the enrichment result can be explained from fixed evidence

If any of the above are false, confidence is below `high` and the enrichment
must not be shown in Slack.

---

## Output Shape

### Slack Output

Only append these lines when confidence is `high`:

```text
RelatedK8sNamespace: <namespace>
RelatedK8sService: <service>
```

Do not emit:

- `LikelyK8sNamespace`
- `LikelyK8sService`
- `EnrichmentConfidence: medium`

First phase should keep Slack wording minimal and conservative.

### Internal Representation

The implementation may carry an optional structure like:

```python
{
    "k8s_enrichment": {
        "namespace": "prod",
        "service": "h2-api",
        "confidence": "high",
        "evidence": {
            "matched_pod_ips": ["10.0.1.12", "10.0.1.13"],
            "matched_pod_names": ["h2-api-abc", "h2-api-def"],
        },
    }
}
```

This structure must remain optional.

Consumers must work correctly when it is absent.

---

## Failure Behavior

Enrichment must fail open in all of these cases:

- target IPs are missing
- target type is not usable for Pod IP correlation
- no Pod matches the target IPs
- more than one candidate `Service` is plausible
- Kubernetes API read fails
- AWS tags are absent or inconsistent

Fail-open means:

- investigation result remains `success`
- original summary remains intact
- no enrichment lines are added to Slack
- no base metadata fields are changed

This phase must never:

- turn a successful AWS investigation into a failed investigation
- overwrite `primary_reason`
- alter `health_state`
- block Slack reply

---

## Implementation Shape

### `openclaw_foundation`

Keep `get_target_group_status` AWS-scoped.

Only minimal changes are acceptable:

- preserve the AWS tool as the source of bounded target group facts
- expose any additional bounded evidence needed by enrichment, such as:
  - registered target IPs
  - optional stable tags if already available from approved AWS read APIs

Do not move Kubernetes correlation logic into the AWS tool.

### `alert_auto_investigator`

Add a post-investigation enrichment step for `target_group` only.

Suggested shape:

- enrichment module under `alert_auto_investigator`
- invoked only after successful `get_target_group_status`
- formatter appends fixed lines only when enrichment confidence is `high`

This keeps the base tool contract stable while allowing product-level,
bounded correlation in the bot layer.

---

## Logging

Add explicit but low-noise logs for enrichment behavior.

Recommended events:

- enrichment started for `target_group`
- enrichment matched high-confidence `namespace/service`
- enrichment skipped because evidence was insufficient
- enrichment failed open because Kubernetes lookup failed

Logs should help runtime validation without polluting normal success output.

---

## Testing

Minimum required coverage:

1. high-confidence enrichment appends `RelatedK8sNamespace` and
   `RelatedK8sService`
2. multiple candidate `Service` results do not surface enrichment
3. no matching Pod IP results in no enrichment
4. Kubernetes API failure results in fail-open behavior
5. non-`target_group` alerts do not run enrichment
6. existing `get_target_group_status` summary and metadata remain unchanged

Testing should include:

- unit tests for evidence evaluation
- handler / formatter tests for Slack output
- regression coverage to prove the original AWS-only reply still works

---

## Acceptance Criteria

Phase 1 is complete when:

- a real non-prod target group alert can enrich to the correct
  `namespace/service`
- Slack output remains unchanged when evidence is not high confidence
- base investigation still replies even when enrichment fails
- no medium-confidence wording leaks into Slack
- existing target group AWS investigation tests still pass

---

## Trade-Offs

### Benefits

- raises the operational value of target group alarms
- stays within deterministic Layer 1 boundaries
- creates a stronger fact surface for future OpenClaw assist

### Costs

- adds bounded product logic in the bot layer
- requires Kubernetes reverse lookup logic and test fixtures
- may still leave some target group alerts without enrichment

That trade-off is acceptable for Phase 1 because the design prioritizes
precision over coverage.

---

## Follow-On Work

If Phase 1 proves useful, later phases may consider:

- stronger AWS tag usage where stable
- optional sample Pod output for high-confidence matches
- OpenClaw Layer 2 interpretation of target group health context

Not before Phase 1:

- medium-confidence Slack output
- workload root cause inference
- Ingress / listener graph reconstruction
