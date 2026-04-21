# Alert Expansion Policy

## Goal

定義 `alert_auto_investigator` 在新增告警支援時的判斷規則，避免每新增一個
alert 就進入大規模 code 改動。

核心目標有三個：

- 優先重用既有 `resource_type` 與 bounded investigation tools
- 把新增成本盡量壓到 fixture / replay / playbook / analysis 層
- 只有在 resource identity 或 evidence model 改變時，才進入新 phase 開發

---

## Core Principle

新告警預設視為：

- **既有資源的新症狀**

而不是：

- **新的 investigation feature**

只有在以下任一條成立時，才應進入 code-level feature work：

- resource identity model changed
- bounded evidence is insufficient
- alert ingress / source schema changed
- deploy / IAM / RBAC boundary changed

其餘情況優先處理：

- fixture
- replay test
- deterministic mapping
- analysis prompt / playbook
- docs

---

## Decision Flow

每次新增告警時，依序回答下列問題。

### 1. Is This An Existing `resource_type`?

先問：

- 這個 alert 能否落到既有 `resource_type`？

例如：

- `RDS CPU`
- `RDS FreeableMemory`
- `RDS ReadIOPS`

都仍然屬於：

- `rds_instance`

再例如：

- `ElastiCache Evictions`
- `ElastiCache DatabaseMemoryUsagePercentage`

都仍然屬於：

- `elasticache_cluster`

若答案是 `yes`，先不要新增新 tool。

若答案是 `no`，進入：

- `Level 3: New Resource Phase`

---

### 2. Is The Existing Evidence Family Already Enough?

再問：

- 既有 bounded tool 是否已能提供足夠的 current-state evidence？

若答案是 `yes`，優先走：

- fixture
- replay
- analysis guidance

若答案是 `no`，進入：

- `Level 2: Evidence Expansion`

---

### 3. Is This Just New Alert Semantics?

再問：

- 只是新的 metric / threshold / alarm wording 嗎？

如果只是：

- 新 metric name
- 新 alert name
- 新 CloudWatch alarm naming
- 新 Prometheus rule naming

但資源辨識與 evidence family 都不變，則：

- 不應新增新 tool
- 不應新增新 runtime branch

而應優先更新：

- replay fixture
- alert-family mapping
- analysis prompt / playbook
- docs

---

### 4. Does This Require New Permissions Or Deployment Changes?

最後問：

- 是否需要新 IAM permission？
- 是否需要新 Kubernetes RBAC？
- 是否需要新的 deploy config / service wiring？

若答案是 `yes`，這已不是低成本擴充，應視為新 phase，
至少補 spec / plan，不要直接 patch 進主線。

---

## Expansion Levels

### Level 1: Low-Cost Expansion

適用條件：

- same `resource_type`
- same evidence family
- existing bounded evidence is sufficient

應做：

- add real-world fixture
- add replay / parser coverage
- add analysis case or playbook guidance
- update docs if needed

不應做：

- new tool
- new adapter
- new runtime branch

#### AWS Examples

- `RDS CPU`
- `RDS FreeableMemory`
- `RDS ReadIOPS`
- `ElastiCache Evictions`

#### Prometheus Examples

- new pod CPU alert that still maps to existing pod resource-usage evidence family
- new deployment rollout alert that still maps to existing deployment status evidence

---

### Level 2: Evidence Expansion

適用條件：

- same `resource_type`
- current evidence family exists conceptually
- but existing bounded evidence is not enough for safe interpretation

應做：

- extend existing tool payload, or add a bounded sibling tool
- update guard / truncation / redaction
- add focused tests
- update analysis input contract

#### Examples

- current `rds_instance` facts are not enough for a high-frequency storage metric family
- pod investigation needs bounded memory evidence but only CPU / events exist
- existing target group evidence lacks one bounded field needed for safe interpretation

---

### Level 3: New Resource Phase

適用條件：

- new `resource_type`
- new identity model
- new dispatcher mapping
- new tool
- new source schema
- new IAM / RBAC / deploy boundary

應做：

- write spec
- write implementation plan
- then implement

#### Examples

- `ReplicationGroupId` support when current ElastiCache support only handles `CacheClusterId`
- `MSK cluster` investigation
- a new ingress source with different structured alert shape

---

## AWS Policy

AWS alert expansion should primarily be judged by:

- resource identity
- bounded current-state evidence sufficiency

### AWS Rule Of Thumb

If multiple alarms still normalize to the same AWS resource and the existing tool
already returns useful bounded state, do not add a new tool per metric.

Instead:

- reuse the same investigation tool
- let deterministic metadata plus analysis layer explain the difference

### Good Pattern

- `RDS CPU` -> `rds_instance` -> `get_rds_instance_status`
- `RDS FreeableMemory` -> `rds_instance` -> `get_rds_instance_status`
- `RDS ReadIOPS` -> `rds_instance` -> `get_rds_instance_status`

The metric-specific meaning belongs in:

- analysis guidance
- playbook wording
- next-step recommendations

not in separate tool definitions.

### AWS Trigger For Level 3

Open a new phase when the identifier model changes.

Examples:

- `CacheClusterId` -> `ReplicationGroupId`
- `DBInstanceIdentifier` -> `DBClusterIdentifier`
- a target-group alert that requires a fundamentally different ownership model

---

## Prometheus Policy

Prometheus alert expansion follows the same high-level rule, but it requires one
extra concept:

- **evidence family**

Why:

- many Prometheus alerts share the same `resource_type`
- but the evidence needed to interpret them can differ significantly

For Prometheus, do not only ask:

- "is this still a pod?"

Also ask:

- "does this alert belong to an existing evidence family?"

### Evidence Family

An evidence family is a bounded set of investigation facts appropriate for a class
of alerts.

Example families for `pod`:

- `pod_runtime_state`
- `pod_failure_signal`
- `pod_resource_usage`
- `pod_rollout_context`

These can map to different combinations of tools, for example:

- `pod_runtime_state`
  - `get_pod_status`
  - `get_pod_events`
- `pod_failure_signal`
  - `get_pod_events`
  - `get_pod_logs`
- `pod_resource_usage`
  - `get_pod_cpu_usage`
  - future bounded memory tool
- `pod_rollout_context`
  - `get_deployment_status`

### Prometheus Rule Of Thumb

If a new alert still belongs to an existing:

- `resource_type`
- evidence family

then expansion should usually stay in:

- fixture
- replay
- mapping
- analysis / playbook

not in new runtime logic.

### Prometheus Trigger For Level 2

Go to evidence expansion when the alert belongs to an existing resource, but the
current evidence family does not provide enough bounded facts.

Example:

- a new pod memory alert arrives
- existing pod tooling can inspect status / events / CPU
- but no bounded memory evidence exists

This is not a new resource phase.
This is an evidence expansion.

### Prometheus Trigger For Level 3

Go to a new phase when:

- the alert identifies a new resource type
- the ingress shape materially changes
- the resource identity cannot be normalized using existing models

---

## What Not To Do

Avoid these patterns:

- one tool per alert name
- one branch per metric family inside the dispatcher
- embedding alert semantics directly into low-level tool names
- using raw CLI output as the default evidence shape

Bad examples:

- `get_pod_high_cpu_context`
- `get_pod_oom_context`
- `get_rds_iops_status`

Prefer evidence-oriented tool names:

- `get_pod_status`
- `get_pod_events`
- `get_pod_logs`
- `get_pod_cpu_usage`
- `get_rds_instance_status`
- `get_elasticache_cluster_status`

---

## Practical Checklist

Before opening a new implementation phase for an alert, check:

1. Does it normalize to an existing `resource_type`?
2. Does it fit an existing evidence family?
3. Is the current bounded evidence sufficient for a conservative interpretation?
4. Does it require new permission or deploy wiring?

Interpretation:

- `yes / yes / yes / no` -> `Level 1`
- `yes / no or not enough / no new deploy boundary` -> `Level 2`
- `no` on resource identity or `yes` on new deploy / permission boundary -> `Level 3`

---

## Summary

Use this policy to keep expansion cost proportional to the real change.

The intended default is:

- new alert -> existing resource -> existing evidence -> fixture + replay + analysis

not:

- new alert -> new tool -> new runtime branch -> new phase

In one sentence:

**Treat new alerts as new symptoms on existing resources unless the resource identity or evidence model has actually changed.**
