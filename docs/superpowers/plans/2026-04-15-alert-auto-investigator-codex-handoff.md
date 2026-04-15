# Alert Auto-Investigator — Codex Handoff Prompt

## Project Overview

This repo (`devops-standards`) implements a production-grade **alert auto-investigator** that:
1. Receives Slack events triggered by CloudWatch Alarms (via Lambda) or Alertmanager
2. Normalizes them into a canonical `NormalizedAlertEvent`
3. Runs a deterministic control plane (ownership → dedup → cooldown → rate limit)
4. Dispatches to **OpenClaw** (an internal read-only investigation engine) when approved
5. Replies to the Slack thread with structured investigation results

The system is **read-only**: OpenClaw only calls tools like `get_pod_events`, `get_pod_status`, `get_deployment_status`. No write operations, no auto-remediation.

---

## Repo Structure

```
devops-standards/
├── openclaw_foundation/          # Core investigation engine (library)
│   └── src/openclaw_foundation/
│       ├── adapters/             # kubernetes.py, prometheus.py (Real + Fake)
│       ├── models/               # requests.py, responses.py, enums.py
│       ├── runtime/              # runner.py, state_machine.py, guards.py
│       └── tools/                # get_pod_events, get_pod_status, get_pod_logs,
│                                 # get_deployment_status, prometheus_*
├── self_service_copilot/         # Existing Slack bot (unrelated, do not modify)
├── alert_auto_investigator/      # NEW SERVICE — primary focus
│   ├── pyproject.toml
│   ├── src/alert_auto_investigator/
│   │   ├── models/
│   │   │   ├── normalized_alert_event.py   # NormalizedAlertEvent dataclass
│   │   │   ├── control_decision.py         # ControlAction enum + ControlDecision
│   │   │   └── control_policy.py           # ControlPolicy (frozen dataclass)
│   │   ├── normalizers/
│   │   │   ├── cloudwatch_alarm.py         # SNS payload → NormalizedAlertEvent
│   │   │   └── alertmanager.py             # Alertmanager alert → NormalizedAlertEvent
│   │   ├── control/
│   │   │   ├── pipeline.py                 # ControlPipeline.evaluate() + record_investigation()
│   │   │   └── store.py                    # AlertStateStore Protocol + InMemoryAlertStateStore
│   │   └── investigation/
│   │       └── dispatcher.py               # OpenClawDispatcher: NormalizedAlertEvent → runner.run()
│   └── tests/                              # 68 tests, all passing
└── backlog/
    ├── normalized-alert-event-v1.md        # NormalizedAlertEvent schema spec
    ├── alert-auto-investigator-backlog.md  # Full backlog with phases
    ├── aws/
    │   ├── lambda.py                       # Current CloudWatch → Slack Lambda
    │   └── message-output.md              # Real CloudWatch SNS payload example
    └── prometheus/
        ├── alert-ex.md                     # Sample Alertmanager alert rule
        ├── configmap-alert.yaml            # Alertmanager config (receivers/routes)
        └── temp_configmap.yaml             # Alertmanager Slack templates (incl. slack.devops.text)
```

---

## What Has Been Built (Do Not Modify)

### `alert_auto_investigator/src/alert_auto_investigator/`

**`models/normalized_alert_event.py`** — `NormalizedAlertEvent` dataclass:
- Required: `schema_version`, `source`, `status`, `environment`, `region_code`, `alert_name`, `alert_key`, `resource_type`, `resource_name`, `summary`, `event_time`
- Optional (default `""`): `account_id`, `cluster`, `severity`, `namespace`, `metric_name`, `description`, `raw_text`; `raw_payload: dict = {}`

**`normalizers/cloudwatch_alarm.py`** — `normalize(payload: dict, environment: str) -> NormalizedAlertEvent`:
- Extracts `region_code` from `AlarmArn` (ARN split on `:`, index 3)
- `NewStateValue`: `ALARM → firing`, `OK → resolved`, other → `unknown`
- `Trigger.Dimensions` → `resource_type`/`resource_name` via mapping:
  `DBInstanceIdentifier → rds_instance`, `InstanceId → ec2_instance`, `LoadBalancer → load_balancer`, `ClusterName → eks_cluster`
- `alert_key`: `cloudwatch_alarm:{account_id}:{region_code}:{alarm_name}`

**`normalizers/alertmanager.py`** — `normalize(alert: dict, environment: str, region_code: str) -> NormalizedAlertEvent`:
- Single alert object from Alertmanager webhook `alerts[]` array
- Resource priority: `pod > deployment > node > instance → unknown`
- `alert_key`: pod/deployment type includes namespace; node type excludes namespace
- `event_time`: firing → `startsAt`, resolved → `endsAt`

**`control/pipeline.py`** — `ControlPipeline.evaluate(event) -> ControlDecision`:
- Gate order: fail-close (empty `alert_key`) → resolved/unknown → ownership → denylist → allowlist → cooldown → rate limit → INVESTIGATE
- `record_investigation(event)` — call after dispatch to update store state

**`control/store.py`** — `InMemoryAlertStateStore`:
- `was_investigated_within(alert_key, seconds) -> bool`
- `record_investigation(alert_key)`
- `count_recent_investigations(window_seconds) -> int`

**`investigation/dispatcher.py`** — `OpenClawDispatcher.dispatch(event, request_id=None) -> CanonicalResponse | None`:
- `DEFAULT_TOOL_ROUTING = {"pod": "get_pod_events", "deployment": "get_deployment_status", "node": "get_pod_events"}`
- Returns `None` if `resource_type` not in routing table
- Builds `InvestigationRequest` with `scope`, `target`, `budget`, `input_ref=f"alert:{alert_key}"`

### Running Tests
```bash
cd alert_auto_investigator
python3.13 -m pytest -v    # 68 tests, all pass
```

---

## Raw Alert Source Formats

### CloudWatch Alarm — Real SNS Payload (`backlog/aws/message-output.md`)

```python
{
  'AlarmName': 'p-rds-shuriken_Blocked_Transactions',
  'AlarmDescription': None,
  'AWSAccountId': '416885395773',
  'NewStateValue': 'OK',          # or 'ALARM'
  'NewStateReason': 'Threshold Crossed: 1 out of the last 1 datapoints [0.0 (13/04/26 15:01:00)] was not greater than or equal to the threshold (4.0) ...',
  'StateChangeTime': '2026-04-13T15:02:59.759+0000',
  'Region': 'Asia Pacific (Tokyo)',
  'AlarmArn': 'arn:aws:cloudwatch:ap-northeast-1:416885395773:alarm:p-rds-shuriken_Blocked_Transactions',
  'OldStateValue': 'ALARM',
  'Trigger': {
    'Period': 60,
    'EvaluationPeriods': 1,
    'Threshold': 4.0,
    'Metrics': [
      {
        'Expression': 'FIRST(SLICE(e1, 0, 1))',
        'Id': 'e2',
        'Label': 'db.Transactions.blocked_transactions',
        'ReturnData': True
      },
      {
        'Expression': "DB_PERF_INSIGHTS('RDS', 'db-E3PGLNOO2FTPO77U4XFVE6PRAE', ['db.Transactions.blocked_transactions.avg', ...])",
        'Id': 'e1',
        'ReturnData': False,
        'Period': 60
      }
    ]
    # NOTE: This alarm uses Metrics (Performance Insights expression), NOT Dimensions.
    # Dimension-based alarms look like:
    # 'Dimensions': [{'name': 'DBInstanceIdentifier', 'value': 'shuriken'}]
  }
}
```

**Critical note**: this real alarm uses `Trigger.Metrics` (Expression-based), **not** `Trigger.Dimensions`.
The `cloudwatch_alarm` normalizer currently only handles `Dimensions`. Alarms using `Metrics`
(Performance Insights, math expressions) produce `resource_type="unknown"`. This is expected
for v1; do not break the existing Dimensions path when adding Metrics support.

The existing Lambda (`backlog/aws/lambda.py`) sends free-form Slack text (not machine-readable).
It must be **updated** to also output a structured machine-readable block in the Slack message.

---

### Alertmanager — Slack Template (`backlog/prometheus/temp_configmap.yaml`)

The `slack.devops.text` template (already deployed) outputs this structured text in Slack:

```
AlertSource: prometheus
Environment: <from labels.environment or labels.env or "unknown">
Cluster: <from labels.cluster or annotations.ClusterName or "unknown">
Severity: <from labels.severity or "unknown">
Status: firing|resolved
AlertName: <from labels.alertname>
ResourceType: job|pod|deployment|service|namespace|host|unknown
ResourceName: <corresponding label value>
Namespace: <from labels.namespace or "-">
Summary: <from annotations.summary or "-">
Description: <from annotations.description or "-">

RawLabels:
- alertname=HttpBlackboxProbeFailed
- cluster=H2-EKS-DEV-STG
- ...
```

This is the **primary machine-readable contract** from Alertmanager.
The investigator bot must parse this text from incoming Slack messages.

Sample alert rule (`backlog/prometheus/alert-ex.md`):
```yaml
- alert: HttpBlackboxProbeFailed
  expr: probe_success{job="blackbox-h2s-backend_api"} == 0
  for: 10m
  labels:
    severity: critical
  annotations:
    summary: Host unusual network throughput out (instance {{ $labels.instance }})
    description: "Http Probe down : {{ $labels }}"
    ClusterName: H2-EKS-DEV-STG
```

---

## Next Tasks (Implement in This Order)

### Task 1 — Slack Message Parser for Alertmanager `slack.devops.text` output

**File**: `alert_auto_investigator/src/alert_auto_investigator/ingress/slack_message_parser.py`

Parse the structured Alertmanager Slack text (the `slack.devops.text` format above) into a `NormalizedAlertEvent`.

```python
def parse_alertmanager_slack_message(
    text: str,
    region_code: str,            # injected from bot config (not in template)
    fallback_environment: str,   # used when Environment == "unknown"
) -> NormalizedAlertEvent | None:
    """Return None if the message is not a valid slack.devops.text block."""
```

Rules:
- Parse `Key: Value` pairs from the structured block (stop at `RawLabels:`)
- `status`: map `firing → firing`, `resolved → resolved`, other → `unknown`
- `resource_type`: use `ResourceType` value directly (already inferred by template)
- `resource_name`: use `ResourceName` value
- `alert_key`: `alertmanager:{cluster}:{namespace}:{alertname}:{resource_name}` for pod/deployment/service;
  `alertmanager:{cluster}:{alertname}:{resource_name}` for node/host/unknown
- If `Environment == "unknown"`, use `fallback_environment`
- Missing required fields → return `None` (fail-close)
- `raw_text`: the full original Slack message text

**Tests**: `tests/test_slack_message_parser.py`
- Parse a valid alertmanager message → correct NormalizedAlertEvent fields
- `Status: resolved` → `status = "resolved"`, returns event (not skipped here; ControlPipeline handles it)
- `Status: pending` → `status = "unknown"`
- Missing AlertName → return `None`
- Environment `"unknown"` → falls back to `fallback_environment`
- `ResourceType: pod` → alert_key includes namespace
- `ResourceType: host` → alert_key excludes namespace

---

### Task 2 — CloudWatch Lambda: add structured machine-readable block to Slack message

**File**: `backlog/aws/lambda.py` (update in-place)

Update the Lambda to append a machine-readable block to its Slack attachment `text` field:

```
--- OpenClaw Block ---
schema_version: v1
source: cloudwatch_alarm
status: ALARM|OK  (raw value; parser will map)
alert_name: <AlarmName>
account_id: <AWSAccountId>
region_code: <extracted from AlarmArn, e.g. ap-northeast-1>
environment: <from ALERT_ENV env var>
event_time: <StateChangeTime>
alert_key: cloudwatch_alarm:<account_id>:<region_code>:<alarm_name>
resource_type: <inferred from Trigger.Dimensions if present, else "unknown">
resource_name: <Dimension value or "unknown">
```

Keep all existing free-text formatting intact. Only append the block.

**File**: `alert_auto_investigator/src/alert_auto_investigator/ingress/slack_message_parser.py`

Add a second parse function:

```python
def parse_cloudwatch_slack_message(text: str) -> NormalizedAlertEvent | None:
    """Parse the '--- OpenClaw Block ---' section from a CloudWatch Lambda Slack message."""
```

Rules:
- Look for `--- OpenClaw Block ---` marker; return `None` if absent
- Parse `key: value` pairs below the marker
- `status`: `ALARM → firing`, `OK → resolved`, other → `unknown`
- `alert_key` is already in the block (extracted from Lambda output); use it directly
- Missing `alert_name` or `alert_key` → return `None`

**Tests**: `tests/test_slack_message_parser.py` (same file)
- Parse a valid CloudWatch block → correct fields
- No `--- OpenClaw Block ---` marker → return `None`
- `status: OK` → `status = "resolved"`

---

### Task 3 — E2E Fixture Tests (normalizer → control → dispatcher)

**File**: `alert_auto_investigator/tests/test_e2e_investigation_flow.py`

Use the **real** CloudWatch SNS payload from `backlog/aws/message-output.md` and a synthetic
Alertmanager alert as fixtures to test the full pipeline without mocking core components.

```python
def test_cloudwatch_alarm_firing_reaches_dispatcher() -> None:
    # Given: real-world-like CloudWatch SNS payload (ALARM state, Dimensions-based alarm)
    # When: normalizer → ControlPipeline.evaluate() → OpenClawDispatcher.dispatch()
    # Then: dispatcher returns a response (not None) for mapped resource_type,
    #       or None with reason documented for unmapped (Performance Insights) alarms

def test_cloudwatch_alarm_ok_is_skipped_by_control_plane() -> None:
    # Given: CloudWatch SNS payload with NewStateValue=OK
    # When: normalize → evaluate
    # Then: decision.action == ControlAction.SKIP, reason contains "resolved"

def test_alertmanager_pod_alert_reaches_dispatcher() -> None:
    # Given: synthetic alertmanager alert dict with pod label
    # When: normalize → evaluate → dispatch
    # Then: dispatcher calls runner with tool_name="get_pod_events"

def test_alertmanager_resolved_alert_is_skipped() -> None:
    # Given: alertmanager alert with status="resolved"
    # When: normalize → evaluate
    # Then: decision.action == SKIP

def test_cooldown_prevents_duplicate_investigation() -> None:
    # Given: same alert_key investigated twice in quick succession
    # When: second evaluate() call on InMemoryAlertStateStore that has record
    # Then: second decision == SKIP with "cooldown" reason

def test_rate_limit_blocks_when_exceeded() -> None:
    # Given: ControlPolicy(rate_limit_count=2) and store with 2 recent investigations
    # When: evaluate()
    # Then: SKIP with "rate limit" reason
```

Use `FakeRunner` (stub) for the dispatcher; do NOT use real Kubernetes/Prometheus adapters.
Use `InMemoryAlertStateStore` (real implementation) for cooldown/rate-limit tests.

---

### Task 4 — `pyproject.toml` dependency update

Add `openclaw-foundation` to `alert_auto_investigator/pyproject.toml` dependencies:
```toml
dependencies = ["openclaw-foundation"]
```

Also update `alert_auto_investigator/pyproject.toml` to add:
```toml
[project.optional-dependencies]
dev = ["pytest>=8.0.0"]
```
(already there, no change needed)

---

## Design Constraints (Do Not Violate)

1. **No LLM in control plane** — all gating is deterministic (status check, ownership, dedup, cooldown, rate limit). LLM is only inside OpenClaw's investigation tools.
2. **Fail-close** — missing `alert_key` or unrecognised `schema_version` → skip, not crash.
3. **`resolved` events never trigger investigation** — enforced in `ControlPipeline.evaluate()` (already implemented).
4. **`InMemoryAlertStateStore` is single-process** — future Redis-backed store will implement the same `AlertStateStore` Protocol without changing `ControlPipeline`.
5. **`OpenClawDispatcher` returns `None`** for unmapped `resource_type` — the caller (future service loop) decides whether to log or skip silently.
6. **`FakeRunner` / stub pattern** — unit tests for the dispatcher must not depend on real `ToolRegistry` or Kubernetes/Prometheus adapters.
7. **Do not modify** `self_service_copilot/` or `openclaw_foundation/` unless the task explicitly targets them.

---

## Coding Conventions

- Python 3.11+, pytest, `setuptools` build backend
- No `try/except` unless at a true system boundary (Slack API, external HTTP)
- No print/debug logging in production code
- Tests use `python3.13 -m pytest -v` from inside `alert_auto_investigator/`
- Naming: `snake_case` for Python, `kebab-case` for K8s resources
- `dataclass(frozen=True)` for config objects; regular `dataclass` for mutable state
- Test file per module: `test_<module_name>.py`
- Helpers shared across tests belong in `tests/conftest.py` (create if needed)
