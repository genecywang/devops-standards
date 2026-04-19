# AWS Alarm Coverage Expansion And ElastiCache Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand AWS alarm coverage for real ElastiCache CloudWatch shapes and add a bounded `elasticache_cluster` investigation path end-to-end.

**Architecture:** Keep `alert_auto_investigator` responsible for deterministic normalization, routing, and Slack formatting while `openclaw_foundation` owns AWS read-only fact gathering and canonical result shaping. Implement the feature in four slices: support posture + parser, golden replay coverage, bounded ElastiCache tooling, and product wiring/docs.

**Tech Stack:** Python 3.11, pytest, boto3 / botocore, Helm docs, CloudWatch structured payload normalization

---

## File Map

### Modify

- `alert_auto_investigator/src/alert_auto_investigator/models/resource_type.py`
  - promote `elasticache_cluster` from `SKIP` to `INVESTIGATE`
- `alert_auto_investigator/src/alert_auto_investigator/investigation/dispatcher.py`
  - route `elasticache_cluster` to `get_elasticache_cluster_status`
- `alert_auto_investigator/src/alert_auto_investigator/normalizers/cloudwatch_alarm.py`
  - keep `CacheClusterId` mapping stable and ensure `CacheNodeId`-bearing alarms still investigate cluster identity
- `alert_auto_investigator/tests/test_cloudwatch_alarm_normalizer.py`
  - cover `CacheClusterId + CacheNodeId` shape
- `alert_auto_investigator/tests/test_openclaw_dispatcher.py`
  - cover dispatcher routing
- `alert_auto_investigator/tests/test_e2e_investigation_flow.py`
  - cover CloudWatch ElastiCache payload reaching dispatcher
- `alert_auto_investigator/tests/test_golden_replays.py`
  - add ElastiCache replay assertions
- `alert_auto_investigator/tests/test_runner_factory.py`
  - verify ElastiCache tool registration
- `alert_auto_investigator/tests/test_handler.py`
  - verify fail-open handler behavior for ElastiCache responses
- `alert_auto_investigator/tests/test_formatter.py`
  - verify deterministic ElastiCache reply shape if formatter path differs from generic AWS formatting
- `alert_auto_investigator/src/alert_auto_investigator/service/runner_factory.py`
  - register `AwsElastiCacheClusterStatusTool`
- `openclaw_foundation/src/openclaw_foundation/adapters/aws.py`
  - add ElastiCache adapter contract and real/fake provider implementation
- `openclaw_foundation/src/openclaw_foundation/runtime/guards.py`
  - add truncation for ElastiCache evidence
- `openclaw_foundation/tests/test_aws_adapter.py`
  - cover fake/real ElastiCache payload mapping and domain error mapping
- `openclaw_foundation/tests/test_runner.py`
  - cover runner execution for ElastiCache tool
- `alert_auto_investigator/docs/support-matrix.md`
  - move `elasticache_cluster` into active support
- `alert_auto_investigator/docs/aws-alarm-inventory.md`
  - update next-phase language and support posture
- `alert_auto_investigator/docs/aws-operations.md`
  - document required ElastiCache read permission and runtime verification

### Create

- `openclaw_foundation/src/openclaw_foundation/tools/aws_elasticache_cluster_status.py`
  - bounded ElastiCache investigation tool
- `openclaw_foundation/tests/test_aws_elasticache_cluster_status_tool.py`
  - tool-level summary and metadata tests
- `alert_auto_investigator/tests/fixtures/cloudwatch_elasticache_alarm.txt`
  - representative structured CloudWatch Slack fixture for replay coverage

---

### Task 1: Promote `elasticache_cluster` To A Routed Resource Type

**Files:**
- Modify: `alert_auto_investigator/src/alert_auto_investigator/models/resource_type.py`
- Modify: `alert_auto_investigator/src/alert_auto_investigator/investigation/dispatcher.py`
- Modify: `alert_auto_investigator/src/alert_auto_investigator/normalizers/cloudwatch_alarm.py`
- Test: `alert_auto_investigator/tests/test_cloudwatch_alarm_normalizer.py`
- Test: `alert_auto_investigator/tests/test_openclaw_dispatcher.py`
- Test: `alert_auto_investigator/tests/test_e2e_investigation_flow.py`

- [ ] **Step 1: Write the failing normalizer and dispatcher tests**

```python
def test_normalize_prefers_cache_cluster_id_when_alarm_also_has_cache_node_id() -> None:
    payload = make_payload(
        dimensions=[
            {"name": "CacheClusterId", "value": "redis-prod-001"},
            {"name": "CacheNodeId", "value": "0001"},
        ],
        namespace="AWS/ElastiCache",
        metric_name="FreeableMemory",
    )

    event = cloudwatch_alarm.normalize(payload, environment="prod-jp")

    assert event.resource_type == "elasticache_cluster"
    assert event.resource_name == "redis-prod-001"


def test_dispatch_routes_elasticache_cluster_to_get_elasticache_cluster_status() -> None:
    runner = RunnerStub()
    dispatcher = OpenClawDispatcher(runner=runner, config=make_config())

    dispatcher.dispatch(make_event(resource_type="elasticache_cluster", resource_name="redis-prod-001"))

    assert runner.last_request.tool_name == "get_elasticache_cluster_status"


def test_cloudwatch_elasticache_alarm_reaches_dispatcher() -> None:
    event = cloudwatch_alarm.normalize(
        make_payload(
            alarm_name="p-elasticache-redis-prod-001_FreeableMemory",
            dimensions=[
                {"name": "CacheClusterId", "value": "redis-prod-001"},
                {"name": "CacheNodeId", "value": "0001"},
            ],
            namespace="AWS/ElastiCache",
            metric_name="FreeableMemory",
        ),
        environment="prod-jp",
    )
    runner = RunnerStub()
    dispatcher = OpenClawDispatcher(runner=runner, config=make_config())

    dispatcher.dispatch(event)

    assert event.resource_type == "elasticache_cluster"
    assert runner.last_request.tool_name == "get_elasticache_cluster_status"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest alert_auto_investigator/tests/test_cloudwatch_alarm_normalizer.py \
  alert_auto_investigator/tests/test_openclaw_dispatcher.py \
  alert_auto_investigator/tests/test_e2e_investigation_flow.py -v
```

Expected:

- FAIL because `elasticache_cluster` is not yet routed as an active investigation type

- [ ] **Step 3: Implement the minimal routing and posture changes**

```python
DEFAULT_TOOL_ROUTING: dict[str, str] = {
    ResourceType.POD: "get_pod_events",
    ResourceType.DEPLOYMENT: "get_deployment_status",
    ResourceType.JOB: "get_job_status",
    ResourceType.CRONJOB: "get_cronjob_status",
    ResourceType.RDS_INSTANCE: "get_rds_instance_status",
    ResourceType.LOAD_BALANCER: "get_load_balancer_status",
    ResourceType.TARGET_GROUP: "get_target_group_status",
    ResourceType.ELASTICACHE_CLUSTER: "get_elasticache_cluster_status",
}


SUPPORT_MATRIX: dict[str, InvestigationPolicy] = {
    ResourceType.RDS_INSTANCE: InvestigationPolicy.INVESTIGATE,
    ResourceType.LOAD_BALANCER: InvestigationPolicy.INVESTIGATE,
    ResourceType.TARGET_GROUP: InvestigationPolicy.INVESTIGATE,
    ResourceType.ELASTICACHE_CLUSTER: InvestigationPolicy.INVESTIGATE,
}
```

- [ ] **Step 4: Keep CloudWatch mapping cluster-bounded**

```python
for dim in dimensions:
    dim_name = dim.get("name", "")
    if dim_name == "CacheClusterId":
        resource_type = ResourceType.ELASTICACHE_CLUSTER
        resource_name = dim.get("value", "unknown")
        break
    if dim_name in _DIMENSION_TO_RESOURCE_TYPE:
        resource_type = _DIMENSION_TO_RESOURCE_TYPE[dim_name]
        resource_name = dim.get("value", "unknown")
        break
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
pytest alert_auto_investigator/tests/test_cloudwatch_alarm_normalizer.py \
  alert_auto_investigator/tests/test_openclaw_dispatcher.py \
  alert_auto_investigator/tests/test_e2e_investigation_flow.py -v
```

Expected:

- PASS

- [ ] **Step 6: Commit**

```bash
git add alert_auto_investigator/src/alert_auto_investigator/models/resource_type.py \
  alert_auto_investigator/src/alert_auto_investigator/investigation/dispatcher.py \
  alert_auto_investigator/src/alert_auto_investigator/normalizers/cloudwatch_alarm.py \
  alert_auto_investigator/tests/test_cloudwatch_alarm_normalizer.py \
  alert_auto_investigator/tests/test_openclaw_dispatcher.py \
  alert_auto_investigator/tests/test_e2e_investigation_flow.py
git commit -m "feat(alert-auto-investigator): route elasticache alarms"
```

---

### Task 2: Add Golden Replay Coverage For Real ElastiCache Alarm Shape

**Files:**
- Create: `alert_auto_investigator/tests/fixtures/cloudwatch_elasticache_alarm.txt`
- Modify: `alert_auto_investigator/tests/test_golden_replays.py`

- [ ] **Step 1: Write the failing replay tests**

```python
def test_golden_parser_cloudwatch_elasticache_replay() -> None:
    event = parse_cloudwatch_alarm_message(_load_fixture("cloudwatch_elasticache_alarm.txt"))

    assert event.alert_name == "p-elasticache-redis-prod-001_FreeableMemory"
    assert event.resource_type == "elasticache_cluster"
    assert event.resource_name == "redis-prod-001"
    assert event.namespace == "AWS/ElastiCache"


def test_golden_cloudwatch_elasticache_replay_reaches_dispatcher() -> None:
    event = parse_cloudwatch_alarm_message(_load_fixture("cloudwatch_elasticache_alarm.txt"))
    runner = _RunnerStub()
    dispatcher = OpenClawDispatcher(
        runner=runner,
        config=InvestigationConfig(tool_routing=dict(DEFAULT_TOOL_ROUTING)),
    )

    dispatcher.dispatch(event)

    assert runner.last_request.tool_name == "get_elasticache_cluster_status"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest alert_auto_investigator/tests/test_golden_replays.py -v
```

Expected:

- FAIL because the fixture and replay assertions do not exist yet

- [ ] **Step 3: Add a representative structured CloudWatch fixture**

```text
Alert: p-elasticache-redis-prod-001_FreeableMemory
source: cloudwatch_alarm
resource_type: elasticache_cluster
resource_name: redis-prod-001
namespace: AWS/ElastiCache
metric_name: FreeableMemory
Trigger.Dimensions:
- CacheClusterId=redis-prod-001
- CacheNodeId=0001
```

- [ ] **Step 4: Add replay assertions using the existing CloudWatch parser path**

```python
def _parse_cloudwatch_fixture(name: str) -> NormalizedAlertEvent:
    payload = json.loads(_load_fixture(name))
    return normalize_cloudwatch_alarm(payload, environment="prod-jp")
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
pytest alert_auto_investigator/tests/test_golden_replays.py -v
```

Expected:

- PASS

- [ ] **Step 6: Commit**

```bash
git add alert_auto_investigator/tests/fixtures/cloudwatch_elasticache_alarm.txt \
  alert_auto_investigator/tests/test_golden_replays.py
git commit -m "test(alert-auto-investigator): add elasticache golden replay"
```

---

### Task 3: Add Bounded ElastiCache Read-Only Adapter And Tool

**Files:**
- Modify: `openclaw_foundation/src/openclaw_foundation/adapters/aws.py`
- Modify: `openclaw_foundation/src/openclaw_foundation/runtime/guards.py`
- Create: `openclaw_foundation/src/openclaw_foundation/tools/aws_elasticache_cluster_status.py`
- Test: `openclaw_foundation/tests/test_aws_adapter.py`
- Test: `openclaw_foundation/tests/test_aws_elasticache_cluster_status_tool.py`
- Test: `openclaw_foundation/tests/test_runner.py`

- [ ] **Step 1: Write the failing adapter and tool tests**

```python
def test_fake_adapter_returns_bounded_elasticache_payload() -> None:
    adapter = FakeAwsProviderAdapter()

    result = adapter.get_elasticache_cluster_status(
        region_code="ap-northeast-1",
        cache_cluster_id="redis-prod-001",
    )

    assert result["cache_cluster_id"] == "redis-prod-001"
    assert result["cache_cluster_status"] == "available"
    assert result["num_cache_nodes"] == 2


def test_real_adapter_maps_elasticache_cluster_payload() -> None:
    elasticache_client = Mock()
    elasticache_client.describe_cache_clusters.return_value = {
        "CacheClusters": [
            {
                "CacheClusterId": "redis-prod-001",
                "Engine": "redis",
                "EngineVersion": "7.1",
                "CacheClusterStatus": "available",
                "NumCacheNodes": 2,
                "ReplicationGroupId": "redis-prod",
                "CacheNodes": [
                    {"CacheNodeId": "0001", "CacheNodeStatus": "available"},
                    {"CacheNodeId": "0002", "CacheNodeStatus": "available"},
                ],
            }
        ]
    }

    adapter = RealAwsProviderAdapter(elasticache_client_factory=lambda region: elasticache_client)

    result = adapter.get_elasticache_cluster_status("ap-northeast-1", "redis-prod-001")

    assert result["cache_cluster_id"] == "redis-prod-001"
    assert result["node_statuses"] == [
        {"cache_node_id": "0001", "status": "available"},
        {"cache_node_id": "0002", "status": "available"},
    ]


def test_get_elasticache_cluster_status_tool_returns_summary_and_metadata() -> None:
    adapter = Mock()
    adapter.get_elasticache_cluster_status.return_value = {
        "cache_cluster_id": "redis-prod-001",
        "engine": "redis",
        "engine_version": "7.1",
        "cache_cluster_status": "available",
        "num_cache_nodes": 2,
        "node_statuses": [
            {"cache_node_id": "0001", "status": "available"},
            {"cache_node_id": "0002", "status": "available"},
        ],
    }
    tool = AwsElastiCacheClusterStatusTool(adapter=adapter)

    response = tool.execute(make_request(resource_name="redis-prod-001"))

    assert response.summary == "ElastiCache cluster redis-prod-001 is healthy"
    assert response.metadata["health_state"] == "healthy"
    assert response.metadata["primary_reason"] == "available"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest openclaw_foundation/tests/test_aws_adapter.py \
  openclaw_foundation/tests/test_aws_elasticache_cluster_status_tool.py \
  openclaw_foundation/tests/test_runner.py -v
```

Expected:

- FAIL because ElastiCache adapter/tool code does not exist yet

- [ ] **Step 3: Add the AWS adapter contract and fake implementation**

```python
class AwsProviderAdapter(Protocol):
    def get_elasticache_cluster_status(self, region_code: str, cache_cluster_id: str) -> dict[str, object]: ...


class FakeAwsProviderAdapter:
    def get_elasticache_cluster_status(self, region_code: str, cache_cluster_id: str) -> dict[str, object]:
        return {
            "cache_cluster_id": cache_cluster_id,
            "engine": "redis",
            "engine_version": "7.1",
            "cache_cluster_status": "available",
            "num_cache_nodes": 2,
            "node_statuses": [
                {"cache_node_id": "0001", "status": "available"},
                {"cache_node_id": "0002", "status": "available"},
            ],
        }
```

- [ ] **Step 4: Implement the real adapter mapping and bounded truncation**

```python
def get_elasticache_cluster_status(
    self,
    region_code: str,
    cache_cluster_id: str,
) -> dict[str, object]:
    client = self._elasticache_client_factory(region_code)
    response = client.describe_cache_clusters(
        CacheClusterId=cache_cluster_id,
        ShowCacheNodeInfo=True,
    )
    clusters = response.get("CacheClusters", [])
    if not clusters:
        raise AwsResourceNotFoundError("elasticache cluster not found")

    cluster = clusters[0]
    return {
        "cache_cluster_id": str(cluster.get("CacheClusterId") or cache_cluster_id),
        "engine": str(cluster.get("Engine") or "unknown"),
        "engine_version": str(cluster.get("EngineVersion") or "unknown"),
        "cache_cluster_status": str(cluster.get("CacheClusterStatus") or "unknown"),
        "num_cache_nodes": int(cluster.get("NumCacheNodes") or 0),
        "replication_group_id": str(cluster.get("ReplicationGroupId") or ""),
        "node_statuses": [
            {
                "cache_node_id": str(node.get("CacheNodeId") or ""),
                "status": str(node.get("CacheNodeStatus") or "unknown"),
            }
            for node in cluster.get("CacheNodes", [])
        ],
    }
```

- [ ] **Step 5: Add the bounded tool summary and metadata rules**

```python
if status == "available":
    summary = f"ElastiCache cluster {cache_cluster_id} is healthy"
    metadata = {
        "health_state": "healthy",
        "attention_required": False,
        "resource_exists": True,
        "primary_reason": "available",
    }
elif status in {"creating"}:
    summary = f"ElastiCache cluster {cache_cluster_id} is in progress: status={status}"
    metadata = {
        "health_state": "in_progress",
        "attention_required": True,
        "resource_exists": True,
        "primary_reason": status,
    }
else:
    summary = f"ElastiCache cluster {cache_cluster_id} is degraded: status={status}"
    metadata = {
        "health_state": "degraded",
        "attention_required": True,
        "resource_exists": True,
        "primary_reason": status,
    }
```

- [ ] **Step 6: Run tests to verify they pass**

Run:

```bash
pytest openclaw_foundation/tests/test_aws_adapter.py \
  openclaw_foundation/tests/test_aws_elasticache_cluster_status_tool.py \
  openclaw_foundation/tests/test_runner.py -v
```

Expected:

- PASS

- [ ] **Step 7: Commit**

```bash
git add openclaw_foundation/src/openclaw_foundation/adapters/aws.py \
  openclaw_foundation/src/openclaw_foundation/runtime/guards.py \
  openclaw_foundation/src/openclaw_foundation/tools/aws_elasticache_cluster_status.py \
  openclaw_foundation/tests/test_aws_adapter.py \
  openclaw_foundation/tests/test_aws_elasticache_cluster_status_tool.py \
  openclaw_foundation/tests/test_runner.py
git commit -m "feat(openclaw-foundation): add elasticache cluster status tool"
```

---

### Task 4: Wire ElastiCache Tool Into Product Runner And Product Tests

**Files:**
- Modify: `alert_auto_investigator/src/alert_auto_investigator/service/runner_factory.py`
- Modify: `alert_auto_investigator/tests/test_runner_factory.py`
- Modify: `alert_auto_investigator/tests/test_handler.py`
- Modify: `alert_auto_investigator/tests/test_formatter.py`

- [ ] **Step 1: Write the failing product wiring tests**

```python
def test_build_tool_registry_registers_elasticache_tool() -> None:
    registry = build_tool_registry()

    assert registry.get("get_elasticache_cluster_status").tool_name == "get_elasticache_cluster_status"


def test_handler_formats_elasticache_investigation_reply() -> None:
    response = CanonicalResponse(
        request_id="req-123",
        result_state=ResultState.SUCCESS,
        summary="ElastiCache cluster redis-prod-001 is healthy",
        actions_attempted=["get_elasticache_cluster_status"],
        metadata={
            "health_state": "healthy",
            "attention_required": False,
            "resource_exists": True,
            "primary_reason": "available",
        },
    )
    reply = format_investigation_reply(
        make_event(resource_type="elasticache_cluster", resource_name="redis-prod-001"),
        response,
    )

    assert "*State:* healthy" in reply
    assert "*Reason:* available" in reply
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest alert_auto_investigator/tests/test_runner_factory.py \
  alert_auto_investigator/tests/test_handler.py \
  alert_auto_investigator/tests/test_formatter.py -v
```

Expected:

- FAIL because the ElastiCache tool is not registered yet

- [ ] **Step 3: Register the tool in runner factory**

```python
from openclaw_foundation.tools.aws_elasticache_cluster_status import AwsElastiCacheClusterStatusTool

registry.register(
    AwsElastiCacheClusterStatusTool(adapter=aws_adapter)
)
```

- [ ] **Step 4: Keep handler and formatter on the generic deterministic path**

```python
if response.metadata.get("health_state") in {"healthy", "gone"}:
    # compact format remains valid for ElastiCache as well
    ...
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
pytest alert_auto_investigator/tests/test_runner_factory.py \
  alert_auto_investigator/tests/test_handler.py \
  alert_auto_investigator/tests/test_formatter.py -v
```

Expected:

- PASS

- [ ] **Step 6: Commit**

```bash
git add alert_auto_investigator/src/alert_auto_investigator/service/runner_factory.py \
  alert_auto_investigator/tests/test_runner_factory.py \
  alert_auto_investigator/tests/test_handler.py \
  alert_auto_investigator/tests/test_formatter.py
git commit -m "feat(alert-auto-investigator): wire elasticache investigation"
```

---

### Task 5: Update Support Docs And AWS Operations Guidance

**Files:**
- Modify: `alert_auto_investigator/docs/support-matrix.md`
- Modify: `alert_auto_investigator/docs/aws-alarm-inventory.md`
- Modify: `alert_auto_investigator/docs/aws-operations.md`

- [ ] **Step 1: Update support matrix wording**

```markdown
| `elasticache_cluster` | `get_elasticache_cluster_status` | CloudWatch alarm (dimension: `CacheClusterId`) |
```

- [ ] **Step 2: Update AWS inventory posture**

```markdown
- `elasticache_cluster` is now implemented as a bounded read-only investigation tool
- `msk_cluster` remains the next larger AWS candidate but is intentionally deferred
```

- [ ] **Step 3: Document minimum AWS read permission and verification**

```markdown
Required IAM:

- `elasticache:DescribeCacheClusters`

Suggested verification:

```bash
pytest openclaw_foundation/tests/test_aws_adapter.py \
  openclaw_foundation/tests/test_aws_elasticache_cluster_status_tool.py \
  alert_auto_investigator/tests/test_golden_replays.py -v
```
```

- [ ] **Step 4: Review docs for consistency with Phase 1 boundary**

```markdown
- no AI assist
- no write action
- no ElastiCache root cause inference
```

- [ ] **Step 5: Commit**

```bash
git add alert_auto_investigator/docs/support-matrix.md \
  alert_auto_investigator/docs/aws-alarm-inventory.md \
  alert_auto_investigator/docs/aws-operations.md
git commit -m "docs(alert-auto-investigator): document elasticache investigation"
```

---

### Task 6: Run Focused Verification And Regression

**Files:**
- No code changes required unless a failing regression reveals a defect

- [ ] **Step 1: Run focused ElastiCache and AWS investigation coverage**

Run:

```bash
pytest openclaw_foundation/tests/test_aws_adapter.py \
  openclaw_foundation/tests/test_aws_elasticache_cluster_status_tool.py \
  openclaw_foundation/tests/test_runner.py \
  alert_auto_investigator/tests/test_cloudwatch_alarm_normalizer.py \
  alert_auto_investigator/tests/test_openclaw_dispatcher.py \
  alert_auto_investigator/tests/test_e2e_investigation_flow.py \
  alert_auto_investigator/tests/test_golden_replays.py \
  alert_auto_investigator/tests/test_runner_factory.py \
  alert_auto_investigator/tests/test_handler.py \
  alert_auto_investigator/tests/test_formatter.py -v
```

Expected:

- PASS

- [ ] **Step 2: Run adjacent AWS regression**

Run:

```bash
pytest openclaw_foundation/tests/test_aws_rds_instance_status_tool.py \
  openclaw_foundation/tests/test_aws_load_balancer_status_tool.py \
  openclaw_foundation/tests/test_aws_target_group_status_tool.py -v
```

Expected:

- PASS

- [ ] **Step 3: Commit final fixes if verification required follow-up changes**

```bash
git add <only files changed during verification follow-up>
git commit -m "test: fix elasticache investigation regressions"
```

If no verification follow-up changes were needed, skip this commit.

---

## Self-Review

- Spec coverage:
  - classification + support posture: Task 1
  - golden replay coverage: Task 2
  - bounded ElastiCache investigation tool: Task 3
  - product wiring and deterministic formatting: Task 4
  - docs / IAM / runtime guidance: Task 5
  - focused verification and adjacent regression: Task 6
- Placeholder scan:
  - no `TBD`, `TODO`, or deferred “write tests later” steps remain
- Type consistency:
  - resource type is consistently `elasticache_cluster`
  - tool name is consistently `get_elasticache_cluster_status`
  - target identity is consistently `cache_cluster_id` / `resource_name`

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-19-aws-elasticache-phase1-implementation-plan.md`.

Per the approved direction, proceed with `Subagent-Driven (recommended)` execution for implementation tasks in this session.
