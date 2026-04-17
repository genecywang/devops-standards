# Alert Auto Investigator — Investigation Support Matrix

This document defines the authoritative list of resource types the bot handles,
and what it does with each. The same policy is enforced in code at
`models/resource_type.py` (`SUPPORT_MATRIX`).

---

## Actively Supported (`INVESTIGATE`)

These resource types trigger a real investigation via an OpenClaw tool.

| resource_type | Tool | Alert Source |
|---------------|------|--------------|
| `pod` | `get_pod_events` | Alertmanager (label: `pod`) |
| `deployment` | `get_deployment_status` | Alertmanager (label: `deployment`) |
| `job` | `get_job_status` | Alertmanager (label: `job_name` or `exported_job`) |

---

## Next Candidates (`NEXT_CANDIDATE`)

Known resource types with investigation value. Currently skipped. A `NEXT_CANDIDATE`
in the dispatcher logs `next_candidate_not_yet_implemented` at INFO so coverage
gaps are visible without being noisy.

| resource_type | Prerequisite before implementing |
|---------------|----------------------------------|
| `cronjob` | Alertmanager template must map `cronjob` to `resource_type=cronjob`; decide whether to investigate CronJob directly or notify-only |
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
