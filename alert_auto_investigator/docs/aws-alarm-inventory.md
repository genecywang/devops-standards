# Alert Auto Investigator — AWS Alarm Inventory

This document summarizes the current AWS CloudWatch alarm surface observed from:

- `backlog/aws/describe-alarms.json`
- `backlog/aws/describe-alarm-history-7d.json`

The goal is to decide AWS support posture from real alarm distribution rather
than extending parser and investigation code blindly.

---

## Current Status

Current AWS support is **parse-first, investigate-later**.

What already exists:

- CloudWatch Slack message emits a machine-readable block
- `cloudwatch_alarm` normalization exists
- current resource mapping supports:
  - `rds_instance`
  - `ec2_instance`
  - `load_balancer`
  - `eks_cluster`
- AWS alerts are currently treated as `SKIP` in `SUPPORT_MATRIX`

This means AWS alerts are recognized, keyed, and controlled, but they do not
yet enter a real investigation tool path.

---

## Observed Inventory

From `describe-alarms.json`:

- total alarms observed: `171`

Top CloudWatch namespaces:

| Namespace | Count | Notes |
|-----------|-------|-------|
| `AWS/Kafka` | `39` | mostly MSK lag / broker metrics |
| `AWS/RDS` | `29` | clear candidate for bounded investigation |
| `AWS/ElastiCache` | `29` | common but currently unmapped |
| `AWS/ApplicationELB` | `25` | clear load-balancer / target-group identity |
| `AWS/WAFV2` | `21` | security / policy domain, likely notify-only first |
| `CWAgent` | `6` | host / node-like signal, not a good first candidate |
| `AWS/EC2` | `5` | low count, infra-generalist surface |
| `AWS/SQS` | `5` | queue-specific operational surface |

Top metrics observed:

| Namespace | Metric | Count |
|-----------|--------|-------|
| `AWS/Kafka` | `SumOffsetLag` | `26` |
| `AWS/WAFV2` | `CountedRequests` | `19` |
| `AWS/ElastiCache` | `FreeableMemory` | `10` |
| `AWS/ApplicationELB` | `TargetResponseTime` | `9` |
| `AWS/ElastiCache` | `DatabaseMemoryUsagePercentage` | `8` |
| `AWS/RDS` | `FreeStorageSpace` | `6` |
| `AWS/RDS` | `CPUUtilization` | `6` |
| `AWS/ApplicationELB` | `UnHealthyHostCount` | `5` |
| `CWAgent` | `mem_used_percent` | `5` |
| `AWS/RDS` | `FreeableMemory` | `5` |

Most common dimension sets:

| Dimensions | Count | Interpretation |
|------------|-------|----------------|
| `DBInstanceIdentifier` | `27` | stable RDS identity |
| `Cluster Name + Consumer Group + Topic` | `24` | Kafka / lag alarms |
| `Region + Rule + WebACL` | `21` | WAF policy alarms |
| `LoadBalancer + TargetGroup` | `16` | target-group / ALB health alarms |
| `CacheClusterId + CacheNodeId` | `15` | ElastiCache node alarms |
| `CacheClusterId` | `14` | ElastiCache cluster alarms |
| `LoadBalancer` | `9` | ALB-level alarms |
| `InstanceId` | `5` | EC2 alarms |

---

## Recent Activity

From `describe-alarm-history-7d.json`:

- total state updates observed over 7 days: `3017`

Top noisy / active alarms:

| AlarmName | Updates | Namespace | Metric |
|-----------|---------|-----------|--------|
| `PROD-ALARM-RDS-SLOWQUERY-SHURIKEN` | `2029` | `Slow Log` | `Shuriken-SlowLogs` |
| `PROD-ALARM-RDS-SLOWQUERY-MICROSERVICE` | `916` | `Slow Log` | `Microservice-SlowLogs` |
| `p-waf-NoUserAgent_HEADER` | `22` | `AWS/WAFV2` | `CountedRequests` |
| `p-rds-shuriken_ReadIOPS` | `20` | `AWS/RDS` | `ReadIOPS` |
| `p-rds-shuriken_Blocked_Transactions` | `8` | `None` | `None` |
| `p-alb-jp-k8s-py3-prod-h2s-wellness-api_HealthyHostCount` | `5` | `AWS/ApplicationELB` | `HealthyHostCount` |
| `p-alb-jp-k8s-py3-prod-h2s-apisvc_HealthyHostCount` | `5` | `AWS/ApplicationELB` | `HealthyHostCount` |

Important observation:

- recent AWS activity is **not dominated by EC2**
- recent signal is concentrated in:
  - RDS
  - ALB
  - WAF
  - custom / slow-log style RDS alarms

This changes the priority order for AWS support.

---

## Current Mapping Gap

Current CloudWatch normalization only maps a small subset of the real observed
dimension vocabulary:

Current supported dimensions:

- `DBInstanceIdentifier` -> `rds_instance`
- `InstanceId` -> `ec2_instance`
- `LoadBalancer` -> `load_balancer`
- `TargetGroup` -> `target_group`
- `ClusterName` -> `eks_cluster`
- `Cluster Name` -> `msk_cluster`
- `CacheClusterId` -> `elasticache_cluster`
- `QueueName` -> `sqs_queue`
- `WebACL` -> `waf_web_acl`

Frequently observed but currently unmapped dimensions:

- `Cluster Name`
- `Consumer Group`
- `Topic`
- `CacheClusterId`
- `CacheNodeId`
- `TargetGroup`
- `QueueName`
- `WebACL`
- `Rule`

Implication:

- many real AWS alarms will currently normalize to `resource_type=unknown`
- parser support is narrower than the real production alarm surface

---

## Recommended Support Posture

This section is a posture recommendation, not an implementation commitment.

### 1. Investigate Candidate

These look like the best first candidates for bounded AWS investigation support.

| resource area | Why |
|---------------|-----|
| `rds_instance` | strong identity via `DBInstanceIdentifier`; high operational value; bounded API surface |
| `load_balancer` / `target_group` | clear ALB health signals; stable AWS APIs; strong relation to user-visible impact |

### 2. Notify-Only First

These should be explicitly classified but not investigated yet.

| resource area | Why |
|---------------|-----|
| `msk_cluster` / Kafka lag | high volume and useful, but investigation surface is broader and needs careful scoping |
| `elasticache_cluster` | common in inventory, but not yet modeled and not the best first AWS tool |
| `waf_web_acl` | important security signal, but not a good fit for the current workload investigation plane |
| `sqs_queue` | queue-specific runbooks likely differ from current triage patterns |

### 3. Skip For Now

| resource area | Why |
|---------------|-----|
| `ec2_instance` | infra-generalist surface; low observed count; easy to become an unbounded diagnostics path |
| `eks_cluster` | cluster-level AWS alarms are too broad for the current narrow investigation model |

---

## Recommended Next AWS Phase

The next AWS phase should **not** start with an AWS API tool.

It should start with:

### Phase AWS-1: Source Inventory And Mapping Expansion

1. formalize AWS support posture from this inventory
2. expand CloudWatch dimension -> `resource_type` mapping for common real alarms
3. add golden replay coverage for representative AWS alarm shapes
4. keep new AWS types as `NEXT_CANDIDATE` or `SKIP` until real investigation tools exist

Only after that:

### Phase AWS-2: First Bounded AWS Investigation Tool

Start with:

- `rds_instance`

Possible first tool shape:

- describe current DB instance state
- capture coarse health / status / class / storage posture
- avoid freeform RDS diagnostics or write actions

---

## Practical Decision

Based on the current inventory:

- AWS support should continue
- but it should not be modeled as just `rds_instance/ec2_instance/load_balancer/eks_cluster`
- first implementation work should go into **classification and source coverage**
- first real AWS investigation candidate should likely be `rds_instance`
