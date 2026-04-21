# Alert Auto Investigator — AWS Operations Guide

This guide documents how to run and verify the current AWS investigation
surface in real environments.

It is intentionally operational, not architectural.

Current supported AWS investigation targets:

- `rds_instance`
- `elasticache_cluster`
- `target_group`
- `load_balancer`

These are all bounded, read-only investigation paths.

---

## 1. Deployment Model

The recommended production model is:

- IAM role managed outside the app chart
- existing Kubernetes ServiceAccount already bound to that IAM role
- Helm chart configured to **use** that existing ServiceAccount

Recommended Helm values:

```yaml
serviceAccount:
  create: false
  name: alert-auto-investigator
```

Why:

- AWS identity lifecycle stays separate from app rollout
- role changes remain auditable in platform / IAM management
- app deploys do not implicitly mutate AWS trust or permissions

The chart still supports a fallback mode where it creates the ServiceAccount and
applies IRSA annotation directly, but that is better suited to temporary or
bootstrap environments than long-lived production usage.

---

## 2.1 Readonly Assist Rollout

The analysis layer MVP should be rolled out in three stages:

1. `off`
2. `shadow`
3. `visible`

Recommended progression:

- start with `off` to confirm chart wiring and env injection
- move to `shadow` to verify analysis output is produced without user-facing impact
- move to `visible` only after shadow output quality and latency are acceptable

Example values:

```yaml
analysis:
  mode: "off"
  provider: stub
  model: claude-3-7-sonnet
  promptVersion: analysis-v1
  outputSchemaVersion: v1
  timeoutSeconds: "10"
  maxInputChars: "4000"
  maxOutputTokens: "500"
```

Verification points:

- `helm template` shows all `OPENCLAW_READONLY_ASSIST_*` env vars rendered
- the pod receives the expected mode and provider via environment variables
- shadow mode produces analysis output but does not change alert handling behavior
- visible mode only ships after you confirm output size and timeout are within bounds

If `analysis.provider=anthropic`, the existing Slack secret must also include:

- `ANTHROPIC_API_KEY`

Rollback:

- set `analysis.mode=off`
- keep the rest of the analysis values unchanged so rollback is a single-value toggle
- re-render and redeploy

---

## 2. Required AWS Permissions

The current AWS tool surface only needs these read-only actions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AlertAutoInvestigatorReadOnlyAws",
      "Effect": "Allow",
      "Action": [
        "rds:DescribeDBInstances",
        "elasticache:DescribeCacheClusters",
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeTargetHealth",
        "elasticloadbalancing:DescribeTags"
      ],
      "Resource": "*"
    }
  ]
}
```

Nothing in AWS phase 1 requires write access.

`DescribeTags` is required for target group single-IP tag fallback.

---

## 3. Required Kubernetes Read Permissions

Target group K8s enrichment also needs these read-only Kubernetes permissions:

- core/v1 `pods`: `get`, `list`, `watch`
- core/v1 `pods/status`: `get`, `list`, `watch`
- core/v1 `events`: `get`, `list`, `watch`
- core/v1 `services`: `get`, `list`, `watch`
- discovery.k8s.io/v1 `endpointslices`: `get`, `list`, `watch`

If `services` or `endpointslices` are missing, base AWS target group replies still
work, but K8s enrichment will fail open and no `RelatedK8sNamespace` /
`RelatedK8sService` lines will be appended.

---

## 4. IRSA / Existing ServiceAccount Checklist

Before runtime testing, confirm these align:

1. Deployment uses the expected ServiceAccount
2. ServiceAccount has the expected role annotation
3. IAM role trust policy uses the correct OIDC provider
4. IAM role trust policy `sub` exactly matches:

```text
system:serviceaccount:<namespace>:<serviceaccount-name>
```

Important:

- `serviceaccount` is singular
- `serviceaccounts` is wrong and will break `AssumeRoleWithWebIdentity`

Useful checks:

```bash
kubectl -n devops get deploy alert-auto-investigator \
  -o jsonpath='{.spec.template.spec.serviceAccountName}{"\n"}'
```

```bash
kubectl -n devops get sa alert-auto-investigator -o yaml
```

```bash
kubectl -n devops exec deploy/alert-auto-investigator -- env | \
  rg 'AWS_ROLE_ARN|AWS_WEB_IDENTITY_TOKEN_FILE'
```

```bash
kubectl -n devops exec deploy/alert-auto-investigator -- python - <<'PY'
import boto3
print(boto3.client("sts").get_caller_identity())
PY
```

If the STS call fails, fix IRSA first. Do not debug tool logic until STS is
working.

---

## 5. Recommended Helm Examples

### Existing ServiceAccount Mode

```bash
helm upgrade --install alert-auto-investigator deploy/charts/alert-auto-investigator \
  -n devops \
  --create-namespace \
  --set image.repository=ghcr.io/genecywang/alert-auto-investigator \
  --set image.tag=sha-<IMAGE_TAG> \
  --set config.provider=real \
  --set config.regionCode=ap-east-2 \
  --set config.fallbackEnvironment=dev-tw \
  --set config.ownedEnvironments=dev-tw \
  --set config.allowedChannelIds=C03GC29TX8C \
  --set config.allowedClusters=H2S-EKS-DEV-STG-EAST-2 \
  --set-string config.allowedNamespaces='dev,monitoring' \
  --set config.prometheusBaseUrl=http://prometheus-operated.monitoring.svc:9090 \
  --set slack.secretName=alert-auto-investigator-slack \
  --set serviceAccount.create=false \
  --set serviceAccount.name=alert-auto-investigator
```

### Chart-Created ServiceAccount With IRSA Annotation

```bash
helm upgrade --install alert-auto-investigator deploy/charts/alert-auto-investigator \
  -n devops \
  --create-namespace \
  --set image.repository=ghcr.io/genecywang/alert-auto-investigator \
  --set image.tag=sha-<IMAGE_TAG> \
  --set config.provider=real \
  --set config.regionCode=ap-east-2 \
  --set config.fallbackEnvironment=dev-tw \
  --set config.ownedEnvironments=dev-tw \
  --set config.allowedChannelIds=C03GC29TX8C \
  --set config.allowedClusters=H2S-EKS-DEV-STG-EAST-2 \
  --set-string config.allowedNamespaces='dev,monitoring' \
  --set config.prometheusBaseUrl=http://prometheus-operated.monitoring.svc:9090 \
  --set slack.secretName=alert-auto-investigator-slack \
  --set serviceAccount.create=true \
  --set-string 'serviceAccount.annotations.eks\.amazonaws\.com/role-arn=arn:aws:iam::<ACCOUNT_ID>:role/alert-auto-investigator'
```

Notes:

- `allowedNamespaces` with commas should use `--set-string`
- annotation keys containing `.` should be escaped in Helm CLI
- if `analysis.provider=anthropic`, the secret referenced by `slack.secretName`
  must also contain `ANTHROPIC_API_KEY`

### Existing ServiceAccount Mode With Anthropic Shadow Analysis

```bash
helm upgrade --install alert-auto-investigator deploy/charts/alert-auto-investigator \
  -n devops \
  --create-namespace \
  --set image.repository=ghcr.io/genecywang/alert-auto-investigator \
  --set image.tag=sha-<IMAGE_TAG> \
  --set config.provider=real \
  --set config.regionCode=ap-east-2 \
  --set config.fallbackEnvironment=dev-tw \
  --set config.ownedEnvironments=dev-tw \
  --set config.allowedChannelIds=C03GC29TX8C \
  --set config.allowedClusters=H2S-EKS-DEV-STG-EAST-2 \
  --set-string config.allowedNamespaces='dev,monitoring' \
  --set config.prometheusBaseUrl=http://prometheus-operated.monitoring.svc:9090 \
  --set slack.secretName=alert-auto-investigator-slack \
  --set serviceAccount.create=false \
  --set serviceAccount.name=alert-auto-investigator \
  --set analysis.mode=shadow \
  --set analysis.provider=anthropic \
  --set analysis.model=claude-3-7-sonnet
```

Anthropic verification:

```bash
kubectl -n devops exec deploy/alert-auto-investigator -- env | \
  rg 'ANTHROPIC_API_KEY|OPENCLAW_READONLY_ASSIST'
```

---

## 6. Manual Replay Templates

The easiest runtime check is to paste a structured CloudWatch alert directly
into Slack.

Always change these fields between replays:

- `alert_name`
- `event_time`
- `alert_key`

This avoids cooldown collisions.

### RDS Example

```text
:fire: [FIRING]
AWS Account : 123456789012
AWS Region : Asia Pacific (Tokyo)
AlarmName : manual-test-rds-cpu-20260419-01
Time : 2026-04-19T10:30:00.000+0000
status : ALARM
message : Manual test for alert auto investigator.

--- Structured Alert ---
schema_version: v1
source: cloudwatch_alarm
status: ALARM
alert_name: manual-test-rds-cpu-20260419-01
account_id: 123456789012
region_code: ap-northeast-1
environment: prod-jp
event_time: 2026-04-19T10:30:00.000+0000
alert_key: cloudwatch_alarm:123456789012:ap-northeast-1:manual-test-rds-cpu-20260419-01
resource_type: rds_instance
resource_name: shuriken
```

### Target Group Example

```text
:fire: [FIRING]
AWS Account : 123456789012
AWS Region : Asia Pacific (Tokyo)
AlarmName : manual-test-target-group-unhealthy-20260419-01
Time : 2026-04-19T10:31:00.000+0000
status : ALARM
message : Manual test for target group investigation.

--- Structured Alert ---
schema_version: v1
source: cloudwatch_alarm
status: ALARM
alert_name: manual-test-target-group-unhealthy-20260419-01
account_id: 123456789012
region_code: ap-northeast-1
environment: prod-jp
event_time: 2026-04-19T10:31:00.000+0000
alert_key: cloudwatch_alarm:123456789012:ap-northeast-1:manual-test-target-group-unhealthy-20260419-01
resource_type: target_group
resource_name: targetgroup/api/abc123
```

### ElastiCache Example

```text
:fire: [FIRING]
AWS Account : 123456789012
AWS Region : Asia Pacific (Tokyo)
AlarmName : manual-test-elasticache-memory-20260419-01
Time : 2026-04-19T10:31:30.000+0000
status : ALARM
message : Manual test for ElastiCache investigation.

--- Structured Alert ---
schema_version: v1
source: cloudwatch_alarm
status: ALARM
alert_name: manual-test-elasticache-memory-20260419-01
account_id: 123456789012
region_code: ap-northeast-1
environment: prod-jp
event_time: 2026-04-19T10:31:30.000+0000
alert_key: cloudwatch_alarm:123456789012:ap-northeast-1:manual-test-elasticache-memory-20260419-01
resource_type: elasticache_cluster
resource_name: redis-prod
```

### Load Balancer Example

```text
:fire: [FIRING]
AWS Account : 123456789012
AWS Region : Asia Pacific (Tokyo)
AlarmName : manual-test-load-balancer-latency-20260419-01
Time : 2026-04-19T10:32:00.000+0000
status : ALARM
message : Manual test for load balancer investigation.

--- Structured Alert ---
schema_version: v1
source: cloudwatch_alarm
status: ALARM
alert_name: manual-test-load-balancer-latency-20260419-01
account_id: 123456789012
region_code: ap-northeast-1
environment: prod-jp
event_time: 2026-04-19T10:32:00.000+0000
alert_key: cloudwatch_alarm:123456789012:ap-northeast-1:manual-test-load-balancer-latency-20260419-01
resource_type: load_balancer
resource_name: app/prod-api/abc123
```

---

## 7. Focused Verification

Recommended focused verification before runtime replay:

```bash
pytest openclaw_foundation/tests/test_aws_adapter.py \
  openclaw_foundation/tests/test_aws_elasticache_cluster_status_tool.py \
  openclaw_foundation/tests/test_aws_rds_instance_status_tool.py \
  openclaw_foundation/tests/test_aws_load_balancer_status_tool.py \
  openclaw_foundation/tests/test_aws_target_group_status_tool.py \
  openclaw_foundation/tests/test_runner.py \
  alert_auto_investigator/tests/test_cloudwatch_alarm_normalizer.py \
  alert_auto_investigator/tests/test_openclaw_dispatcher.py \
  alert_auto_investigator/tests/test_e2e_investigation_flow.py \
  alert_auto_investigator/tests/test_golden_replays.py \
  alert_auto_investigator/tests/test_runner_factory.py -q
```

---

## 8. Runtime Verification

When replaying or observing real AWS alerts, look for these logs:

```bash
kubectl -n devops logs deploy/alert-auto-investigator | \
  rg 'control_decision|dispatch_started|dispatch_failed|investigation_replied|cooldown'
```

Expected success pattern:

- `control_decision action=investigate`
- `dispatch_started resource_type=... tool_name=...`
- `investigation_replied ... resource_type=...`

Expected success examples:

- `rds_instance -> get_rds_instance_status`
- `target_group -> get_target_group_status`
- `load_balancer -> get_load_balancer_status`

If you see `cooldown`, change the replay `alert_key`.

---

## 8. Shadow Rollout Verification

If you want to stage target group enrichment conservatively in production, use a
shadow-style verification pass before relying on the appended K8s lines.

Recommended checks:

1. Deploy the current build with target group enrichment code included.
2. Replay target group alerts that cover:
   - unsupported target types
   - namespace scope misses
   - successful high-confidence matches
3. Watch logs for fail-open behavior instead of Slack regressions:

```bash
kubectl -n devops logs deploy/alert-auto-investigator | \
  rg 'target_group_enrichment_failed|dispatch_started|investigation_replied'
```

4. Confirm the base target group reply still posts even when enrichment does not
   resolve a Kubernetes Service.
5. Confirm `RelatedK8sNamespace` / `RelatedK8sService` only appear for real
   high-confidence cases.

Operational expectation:

- enrichment failure must not suppress the base AWS reply
- missing RBAC or lookup misses should degrade to normal target group output
- only deterministic matches should append K8s identity lines

---

## 9. Known Failure Modes

### `AssumeRoleWithWebIdentity` AccessDenied

Root cause class:

- IRSA trust mismatch

Most common causes:

- trust policy uses `system:serviceaccounts:...` instead of `system:serviceaccount:...`
- wrong namespace in trust policy
- wrong ServiceAccount name in trust policy
- deployment not using the intended ServiceAccount

This is not an app-level bug.

---

### `aws access denied`

Root cause class:

- role exists, but required read permission is missing

Check:

- `rds:DescribeDBInstances`
- `elasticloadbalancing:DescribeLoadBalancers`
- `elasticloadbalancing:DescribeTargetGroups`
- `elasticloadbalancing:DescribeTargetHealth`
- `elasticloadbalancing:DescribeTags`

---

### `NotFound`

Root cause class:

- alert references a resource that no longer exists
- test replay used a fake or stale resource name

This is an expected bounded outcome, not necessarily a bug.

---

### Slack reply contains trailing backticks in AWS resource names

Root cause class:

- structured alert block fenced incorrectly upstream

The machine-readable block should remain plain text, not wrapped in code fences.

---

## 10. Practical Phase-1 Exit Criteria

AWS phase 1 can be considered operationally complete when:

- IRSA or equivalent credential path is stable
- one real or manual replay succeeded for each supported AWS type:
  - `rds_instance`
  - `target_group`
  - `load_balancer`
- deterministic Slack replies look correct
- logs show successful dispatch and reply for those three paths
- no recent credential or parser-format regressions remain open
