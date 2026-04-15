# Normalized Alert Contract

## Objective

Define the minimum normalized alert payload contract that an upstream sender must provide before `self_service_copilot` can apply ownership filtering in a shared Slack channel.

Owner: Self-Service Ops Copilot.

## In Scope

- Slack-visible normalized alert text shape
- minimum required fields for ownership filtering
- optional fields that improve operator context
- fail-closed handling when required fields are missing or invalid

## Out of Scope

- Alertmanager routing configuration
- raw Prometheus rule design
- auto-investigation workflow
- cross-cluster or cross-EKS access
- sender-side implementation details

## Required Fields

| Field | Required | Example | Purpose |
|---|---|---|---|
| `AlertSource` | yes | `prometheus` | identify the alert family used by the ownership gate |
| `Cluster` | yes | `staging-main` | primary ownership key used by the bot |

## Optional Fields

These fields are not required for ownership filtering, but they improve operator readability and future investigation context.

| Field | Example | Purpose |
|---|---|---|
| `AlertName` | `KubePodCrashLooping` | human-readable alert identifier |
| `Severity` | `warning` | operator triage hint |
| `Namespace` | `payments` | optional workload scope |
| `Pod` | `payments-api-123` | optional workload scope |
| `Deployment` | `payments-api` | optional workload scope |
| `Summary` | `Pod restart rate is elevated` | short human-readable context |
| `GeneratorURL` | `https://prometheus.example/...` | source-system reference |

## Canonical Slack Text Shape

Current parsing is line-oriented `Field: value` text. The sender must emit one field per line.

Minimum accepted shape:

```text
AlertSource: prometheus
Cluster: staging-main
```

Recommended shape:

```text
AlertSource: prometheus
Cluster: staging-main
AlertName: KubePodCrashLooping
Severity: warning
Namespace: payments
Pod: payments-api-123
Summary: Pod restart rate is elevated
```

## Contract Rules

- `AlertSource` must equal `prometheus`
- `Cluster` must be the exact cluster name owned by a bot instance, such as `staging-main`, `jp-main`, or `au-main`
- matching is exact string equality; the bot does not infer ownership from free text like `dev`, `jp`, or `au`
- the contract must not rely on raw PromQL, raw Alertmanager JSON, or hidden metadata not present in Slack text
- one Slack message represents one normalized alert contract instance

## Fail-Closed Behavior

If the payload does not satisfy the minimum contract, the bot must not investigate and must not guess.

| Condition | Expected bot behavior |
|---|---|
| `AlertSource` missing | ignore |
| `Cluster` missing | ignore |
| `AlertSource` not equal to `prometheus` | ignore |
| `Cluster` does not match the bot's own cluster | ignore |
| `Cluster` matches the bot's own cluster | local filter only, no Slack reply yet |

Current ownership decision mapping:

- matching cluster -> `source_type=prometheus_alert`, `decision=handled`, `reason=cluster_match`
- non-matching cluster -> `source_type=prometheus_alert`, `decision=ignored`, `reason=not_my_cluster`
- missing required field -> `source_type=unknown`, `decision=ignored`, `reason=unroutable`

## Examples

### Accepted for local filtering

```text
AlertSource: prometheus
Cluster: staging-main
Severity: warning
AlertName: TestOwnershipLocalCluster
```

### Ignored for other cluster

```text
AlertSource: prometheus
Cluster: prod-main
Severity: warning
AlertName: TestOwnershipOtherCluster
```

### Ignored as unroutable

```text
Severity: warning
AlertName: MissingCluster
```

## Validation Guidance

Validate this contract in a shared dev Slack channel before any broader rollout:

1. Post a non-matching cluster alert and confirm there is no Slack reply.
2. Post a matching cluster alert and confirm there is still no Slack reply.
3. Inspect bot logs for the corresponding `ownership decision` line.

See `self_service_copilot/README.md` for the step-by-step dev shared channel validation runbook.
