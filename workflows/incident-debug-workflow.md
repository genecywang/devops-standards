# Incident Debug Workflow

## Sequence

1. Capture symptom as signal.
2. Gather evidence before fixing.
3. Separate facts from hypothesis.
4. Test one hypothesis at a time.
5. Apply the smallest safe fix.
6. Verify recovery.
7. Document rollback and follow-up.

## Evidence Sources

Prefer concrete evidence:

- Kubernetes events and logs.
- CloudWatch metrics and logs.
- AWS API output.
- Prometheus metrics.
- OpenSearch logs.
- CI logs.
- Terraform plan output.
- Helm rendered manifests.

## Response Format

```text
Symptom:
- ...

Facts:
- ...

Hypothesis:
- [推測] ...

Verification:
- command:
- expected signal:

Fix:
- ...

Rollback:
- ...
```

## Production Rule

For production, prioritize:

- Containment.
- Rollback.
- Least-risk mitigation.
- Evidence preservation.
- Post-incident follow-up.
