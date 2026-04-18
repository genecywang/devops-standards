# Alert Auto Investigator — Investigation Support Matrix

This document defines the authoritative list of resource types the bot handles,
and what it does with each. The same policy is enforced in code at
`models/resource_type.py` (`SUPPORT_MATRIX`).

---

## Runtime Behavior Quick Reference

Use this section when reading live Slack alerts. "No reply" is not always a bug.

| Alert shape | Expected bot behavior | Why |
|-------------|-----------------------|-----|
| `pod` in allowed namespace | Replies in thread | `pod` is actively supported |
| short-lived `pod` already deleted before investigation | Replies in thread with `pod <name> no longer exists` | graceful fallback for ephemeral pods |
| `deployment` in allowed namespace | Replies in thread | `deployment` is actively supported |
| `job` in allowed namespace | Replies in thread | `job` is actively supported |
| `cronjob` in allowed namespace | Replies in thread | latest owned Job is investigated and summarized |
| `job` outside `ALLOWED_NAMESPACES` or `ALLOWED_CLUSTERS` | No Slack reply | blocked by runtime scope guard |
| `cronjob` outside `ALLOWED_NAMESPACES` or `ALLOWED_CLUSTERS` | No Slack reply | blocked by runtime scope guard |
| `namespace` | No Slack reply | `SKIP` by design |
| `node` | No Slack reply | `SKIP` by design |
| `unknown` | No Slack reply | parser could not map to a supported investigation target |

Operational notes:

- `pod no longer exists` usually means the alert targeted an ephemeral workload and the pod was already gone when investigation started.
- `job` and `cronjob` alert keys include namespace; cooldown and dedupe are namespace-scoped.
- If a supported alert does not reply, check logs for either:
  - `dispatch_scope_denied`
  - `dispatch_failed`

### Alert Identity vs Investigation Outcome

Slack `Alert:` and investigation output are intentionally **not** a 1:1 semantic
mapping.

- The alert name tells you **which upstream rule fired**
- The investigation tells you **the resource's current state when the bot checked it**

That means different alert names may legitimately converge to the same
investigation result.

Examples:

- `KubernetesJobSlowCompletion` and `KubernetesJobFailed` may both investigate to
  the same current Job state, such as `failed` with
  `primary_reason=BackoffLimitExceeded`
- multiple pod alerts (`NotReady`, `OOMKilled`, `NotInRunningStatus`) may all
  converge to the same current pod outcome, such as `degraded`,
  `primary_reason=OOMKilled`, or `resource_exists=false`

This is expected. The bot is reporting **current resource state**, not replaying
the exact semantics of the original alert rule at firing time.

### Investigation Outcome Taxonomy

Supported investigation results should use a small shared metadata contract:

- `health_state`
- `attention_required`
- `resource_exists`
- `primary_reason`

Current canonical `health_state` values:

| health_state | Meaning | Typical examples |
|--------------|---------|------------------|
| `healthy` | Resource is currently in a good terminal or stable state | running pod without warning signal, completed job |
| `degraded` | Resource exists but is unhealthy or needs operator attention | pending pod, OOMKilled pod, waiting pod |
| `failed` | Resource reached a failed terminal state | job failed with `BackoffLimitExceeded` |
| `in_progress` | Resource is actively running and not yet terminal | active job still running |
| `pending` | Resource exists but has not yet made meaningful progress | job created but neither active nor complete |
| `idle` | Resource is healthy but currently has no active or recent execution | cronjob with no recent jobs |
| `suspended` | Resource is intentionally paused | suspended cronjob |
| `gone` | Resource no longer exists at investigation time | short-lived pod already deleted |

Interpretation rules:

- `attention_required=true` means the current state needs follow-up, even if the original alert rule had different wording
- `resource_exists=false` means the target disappeared before or during investigation; this is not automatically a failure
- `primary_reason` should describe the strongest current signal, not restate the alert name

### Golden Coverage Matrix

This section tracks which support boundaries are pinned by fixture-based
regression tests today. It is intentionally narrower than full runtime support:
if a path is supported in production code but absent here, that means "not yet
golden-covered", not "unsupported".

| resource_type | Scenario | Fixture / test coverage | Covered layers |
|---------------|----------|-------------------------|----------------|
| `job` | failed Job (`BackoffLimitExceeded`) | `alertmanager_job_failed.txt`, `test_golden_parser_job_failed_replay`, `test_golden_formatter_keeps_full_metadata_for_failed_job_reply`, `test_golden_metadata_failed_job_contract` | parser, formatter, tool metadata |
| `job` | slow-completion alert converging to current failed Job state | `alertmanager_job_slow_completion.txt`, `test_golden_parser_job_slow_completion_replay` | parser |
| `deployment` | healthy deployment with all replicas available | `alertmanager_deployment_healthy.txt`, `test_golden_parser_deployment_replay`, `test_golden_formatter_compacts_healthy_deployment_reply`, `test_golden_metadata_healthy_deployment_contract` | parser, formatter, tool metadata |
| `pod` | healthy / stable running pod | `alertmanager_pod_healthy.txt`, `test_golden_formatter_compacts_healthy_pod_reply`, `test_golden_metadata_healthy_pod_contract` | formatter, tool metadata |
| `pod` | pod already deleted before investigation | `alertmanager_pod_gone.txt`, `test_golden_formatter_compacts_gone_pod_reply`, `test_golden_metadata_deleted_pod_contract` | formatter, tool metadata |
| `pod` | degraded pod with OOMKilled signal | `alertmanager_pod_oomkilled.txt`, `test_golden_formatter_keeps_full_metadata_for_degraded_pod_reply`, `test_golden_metadata_degraded_pod_contract` | formatter, tool metadata |
| `cronjob` | suspended cronjob with no recent jobs | `alertmanager_cronjob_suspended.txt`, `test_golden_formatter_compacts_suspended_cronjob_reply`, `test_golden_metadata_suspended_cronjob_contract` | formatter, tool metadata |
| `cronjob` | idle cronjob with no recent jobs | `alertmanager_cronjob_idle.txt`, `test_golden_formatter_keeps_full_metadata_for_idle_cronjob_reply`, `test_golden_metadata_idle_cronjob_contract` | formatter, tool metadata |
| `namespace` | skip-by-design dispatcher miss | `alertmanager_namespace_skip.txt`, `test_golden_skip_by_design_namespace_replay` | parser, dispatcher skip |

Current known gaps:

- `job` does not yet have a fixture asserting formatter output for the slow-completion alert shape
- `cronjob` does not yet have a parser-focused golden replay fixture; current coverage starts at formatter / metadata contract
- multi-alert grouped Slack replay is covered by ordinary tests, but not yet represented as a named golden fixture set here

---

## Actively Supported (`INVESTIGATE`)

These resource types trigger a real investigation via an OpenClaw tool.

| resource_type | Tool | Alert Source |
|---------------|------|--------------|
| `pod` | `get_pod_events` | Alertmanager (label: `pod`) |
| `deployment` | `get_deployment_status` | Alertmanager (label: `deployment`) |
| `job` | `get_job_status` | Alertmanager (label: `job_name` or `exported_job`) |
| `cronjob` | `get_cronjob_status` | Alertmanager (label: `cronjob`) |

### Runtime Scope Guard

`INVESTIGATE` means the bot knows how to route the alert to a real tool. It does
**not** mean every alert of that type will be allowed to execute at runtime.

Actual execution is still constrained by runner scope:

- `ALLOWED_CLUSTERS`
- `ALLOWED_NAMESPACES`

If the alert is supported but outside the configured scope, dispatch is blocked by
policy and no Slack investigation reply is posted. The handler logs:

- `dispatch_scope_denied ... reason=cluster is not allowed`
- `dispatch_scope_denied ... reason=namespace is not allowed`

Example:

- `job` alerts in namespace `monitoring` are fully supported by the code path
- but if `ALLOWED_NAMESPACES` only contains `dev`, the alert is expected to stop
  at scope guard with `dispatch_scope_denied`

This is a policy decision, not a parser failure and not a missing tool mapping.

---

## Next Candidates (`NEXT_CANDIDATE`)

Known resource types with investigation value. Currently skipped. A `NEXT_CANDIDATE`
in the dispatcher logs `next_candidate_not_yet_implemented` at INFO so coverage
gaps are visible without being noisy.

| resource_type | Prerequisite before implementing |
|---------------|----------------------------------|
| `statefulset` | Alertmanager label: `statefulset`; build `get_statefulset_status` tool |
| `daemonset` | Alertmanager label: `daemonset`; build `get_daemonset_status` tool |

> **Important for `job` / `cronjob`**: Prometheus scrape jobs also carry a `job` label
> (e.g. `job=node-exporter` or `job=kubernetes-service-endpoints`). The parser must
> not infer `resource_type=job` from the scrape `job` label. In the current alert rules,
> Kubernetes Job targets are identified by `job_name` or `exported_job`, while CronJob
> targets are identified by `cronjob`.

---

## Skip by Design (`SKIP`)

These resource types are recognised but will never trigger an investigation in this bot.
The dispatcher logs at DEBUG (`skip_by_design`) — no Slack reply is posted.

### Kubernetes Infrastructure

| resource_type | Reason |
|---------------|--------|
| `node` | Host-level alerts; investigation requires node-exporter metrics, not K8s events. Route to infra on-call or a dedicated node runbook. |
| `namespace` | Namespace-scoped alerts are too coarse; no single K8s API call covers them. |

> **`instance` label normalization**: in this system, Alertmanager alerts that identify a
> cluster target via the `instance` label are normalized to `resource_type=node`.
> The reason is architectural, not cosmetic: the investigation plane is K8s-oriented,
> so these alerts are treated as Kubernetes node alerts even if the raw label value is
> a host FQDN or IP. If we later ingest true non-Kubernetes host alerts, `host` should
> be introduced as a new explicit type in `SUPPORT_MATRIX`, not mixed into `node`.

### AWS Resources

| resource_type | Reason |
|---------------|--------|
| `rds_instance` | Requires CloudWatch / RDS API tools not built yet. |
| `ec2_instance` | EC2 metrics live outside K8s; no investigation tool exists. |
| `load_balancer` | ALB / NLB metric investigation is a different domain. |
| `eks_cluster` | Cluster-level alerts need a separate runbook; not scoped to a single workload. |

### Catch-all

| resource_type | Reason |
|---------------|--------|
| `unknown` | Parser could not infer a resource type from alert labels. Alert passes control checks but cannot be dispatched. Fix the upstream alert rule to include an identifiable label. |

---

## Truly Unknown (not in matrix)

If `resource_type` is absent from `SUPPORT_MATRIX` entirely, the dispatcher logs
`unknown_resource_type` at **WARNING**. This indicates a parser gap or a new alert
source not yet accounted for. Add the type to `SUPPORT_MATRIX` before it reaches
production volume.

---

## Adding a New Resource Type

1. Add a constant to `ResourceType` in `models/resource_type.py`.
2. Add an entry to `SUPPORT_MATRIX` — start with `NEXT_CANDIDATE`.
3. Update the relevant normalizer (`normalizers/alertmanager.py` or `normalizers/cloudwatch_alarm.py`) to emit the new constant.
4. Build and register the OpenClaw tool in `service/runner_factory.py`.
5. Add the routing entry to `DEFAULT_TOOL_ROUTING` in `investigation/dispatcher.py` and change the policy to `INVESTIGATE`.
6. Update this document.
7. Verify runtime scope for the new type:
   - ensure expected `ALLOWED_CLUSTERS` / `ALLOWED_NAMESPACES` values are present in deployment config
   - if the type should stay supported-but-restricted, document that policy explicitly
