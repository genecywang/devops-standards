# Ownership Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal ownership gate so each `self_service_copilot` instance only handles Slack messages that target its own environment or cluster.

**Architecture:** Keep the existing parser, dispatcher, and runner boundaries. Add a thin ownership decision layer in `bot.py` before dispatch. Manual commands use `requested_environment` matching, while normalized Prometheus alerts use `cluster-first` matching from Slack text.

**Tech Stack:** Python 3, Slack Bolt, pytest, existing `self_service_copilot` config/parser/dispatcher modules

---

## File Map

- Modify: `self_service_copilot/src/self_service_copilot/config.py`
  Add explicit bot identity accessors and validation helpers for ownership checks.
- Create: `self_service_copilot/src/self_service_copilot/ownership.py`
  Parse message source type and make ownership decisions for manual commands and Prometheus alerts.
- Modify: `self_service_copilot/src/self_service_copilot/bot.py`
  Run ownership gate before existing parse / dispatch / runner flow and add ownership decision logging.
- Modify: `self_service_copilot/tests/test_config.py`
  Cover config identity defaults and parsing expectations.
- Create: `self_service_copilot/tests/test_ownership.py`
  Cover manual command and Prometheus alert ownership matching.
- Modify: `self_service_copilot/tests/test_bot.py`
  Verify ignored messages do not reply and matched messages still use existing flow.
- Modify: `self_service_copilot/README.md`
  Document bot identity, ownership rules, and shared-channel behavior.

### Task 1: Add Ownership Identity to Config

**Files:**
- Modify: `self_service_copilot/src/self_service_copilot/config.py`
- Test: `self_service_copilot/tests/test_config.py`

- [ ] **Step 1: Write the failing config tests**

```python
def test_from_env_uses_environment_and_cluster_as_bot_identity(monkeypatch):
    monkeypatch.setenv("COPILOT_CLUSTER", "jp-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "jp")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "jp-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "payments")

    config = CopilotConfig.from_env()

    assert config.cluster == "jp-main"
    assert config.environment == "jp"


def test_environment_clusters_defaults_to_bot_cluster(monkeypatch):
    monkeypatch.setenv("COPILOT_CLUSTER", "dev-stg-main")
    monkeypatch.setenv("COPILOT_ENVIRONMENT", "dev-stg")
    monkeypatch.setenv("COPILOT_ALLOWED_CLUSTERS", "dev-stg-main")
    monkeypatch.setenv("COPILOT_ALLOWED_NAMESPACES", "monitoring")

    config = CopilotConfig.from_env()

    assert config.default_environment == "dev-stg"
    assert config.environment_clusters == {"dev-stg": "dev-stg-main"}
```

- [ ] **Step 2: Run test to verify it fails only if identity behavior is missing**

Run: `cd /Users/genewang/Project/genecywang/devops-standards && self_service_copilot/.venv/bin/python -m pytest self_service_copilot/tests/test_config.py -q`

Expected: existing tests pass or one new assertion fails around missing identity semantics.

- [ ] **Step 3: Implement minimal config cleanup**

```python
@dataclass(kw_only=True)
class CopilotConfig:
    cluster: str
    environment: str
    default_environment: str = ""
    environment_clusters: dict[str, str] = field(default_factory=dict)
    ...

    def __post_init__(self) -> None:
        if not self.default_environment:
            self.default_environment = self.environment
        if not self.environment_clusters:
            self.environment_clusters = {self.default_environment: self.cluster}
```

Implementation note:
- Keep `cluster` and `environment` as the bot's identity.
- Do not add AWS identity yet.

- [ ] **Step 4: Run test to verify config behavior**

Run: `cd /Users/genewang/Project/genecywang/devops-standards && self_service_copilot/.venv/bin/python -m pytest self_service_copilot/tests/test_config.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add self_service_copilot/src/self_service_copilot/config.py self_service_copilot/tests/test_config.py
git commit -m "feat: define copilot bot identity config"
```

### Task 2: Add Ownership Decision Helper

**Files:**
- Create: `self_service_copilot/src/self_service_copilot/ownership.py`
- Create: `self_service_copilot/tests/test_ownership.py`

- [ ] **Step 1: Write the failing ownership tests**

```python
def test_manual_command_matches_same_environment():
    decision = decide_ownership(
        text="<@U123> jp get_pod_status payments api-123",
        bot_user_id="U123",
        supported_tools=frozenset({"get_pod_status"}),
        my_environment="jp",
        my_cluster="jp-main",
    )

    assert decision.decision == "handled"
    assert decision.source_type == "manual_command"
    assert decision.reason == "environment_match"


def test_manual_command_for_other_environment_is_ignored():
    decision = decide_ownership(
        text="<@U123> au get_pod_status payments api-123",
        bot_user_id="U123",
        supported_tools=frozenset({"get_pod_status"}),
        my_environment="jp",
        my_cluster="jp-main",
    )

    assert decision.decision == "ignored"
    assert decision.reason == "not_my_environment"


def test_prometheus_alert_matches_same_cluster():
    decision = decide_ownership(
        text="AlertSource: prometheus\nCluster: jp-main\nSeverity: warning",
        bot_user_id="U123",
        supported_tools=frozenset({"get_pod_status"}),
        my_environment="jp",
        my_cluster="jp-main",
    )

    assert decision.decision == "handled"
    assert decision.source_type == "prometheus_alert"
    assert decision.reason == "cluster_match"


def test_prometheus_alert_without_match_is_ignored():
    decision = decide_ownership(
        text="AlertSource: prometheus\nCluster: au-main\nSeverity: warning",
        bot_user_id="U123",
        supported_tools=frozenset({"get_pod_status"}),
        my_environment="jp",
        my_cluster="jp-main",
    )

    assert decision.decision == "ignored"
    assert decision.reason == "not_my_cluster"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/genewang/Project/genecywang/devops-standards && self_service_copilot/.venv/bin/python -m pytest self_service_copilot/tests/test_ownership.py -q`

Expected: FAIL because `ownership.py` does not exist yet

- [ ] **Step 3: Write minimal ownership helper**

```python
@dataclass(frozen=True)
class OwnershipDecision:
    source_type: str
    decision: str
    reason: str
    target_environment: str | None = None
    target_cluster: str | None = None


def decide_ownership(
    *,
    text: str,
    bot_user_id: str,
    supported_tools: frozenset[str],
    my_environment: str,
    my_cluster: str,
) -> OwnershipDecision:
    if _looks_like_manual_command(text, bot_user_id):
        cmd = parse(text, bot_user_id, supported_tools)
        if cmd.requested_environment is None:
            return OwnershipDecision(
                source_type="manual_command",
                decision="ignored",
                reason="missing_environment",
            )
        if cmd.requested_environment != my_environment:
            return OwnershipDecision(
                source_type="manual_command",
                decision="ignored",
                reason="not_my_environment",
                target_environment=cmd.requested_environment,
            )
        return OwnershipDecision(
            source_type="manual_command",
            decision="handled",
            reason="environment_match",
            target_environment=cmd.requested_environment,
        )

    cluster = _extract_field(text, "Cluster")
    alert_source = _extract_field(text, "AlertSource")
    if alert_source == "prometheus" and cluster:
        return OwnershipDecision(
            source_type="prometheus_alert",
            decision="handled" if cluster == my_cluster else "ignored",
            reason="cluster_match" if cluster == my_cluster else "not_my_cluster",
            target_cluster=cluster,
        )

    return OwnershipDecision(
        source_type="unknown",
        decision="ignored",
        reason="unroutable",
    )
```

Implementation notes:
- Reuse existing `parse()` for manual commands.
- Do not reply from this helper.
- Keep matching rules intentionally narrow: manual command and normalized Prometheus alert only.

- [ ] **Step 4: Run tests to verify helper behavior**

Run: `cd /Users/genewang/Project/genecywang/devops-standards && self_service_copilot/.venv/bin/python -m pytest self_service_copilot/tests/test_ownership.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add self_service_copilot/src/self_service_copilot/ownership.py self_service_copilot/tests/test_ownership.py
git commit -m "feat: add slack ownership decision helper"
```

### Task 3: Gate Slack Handling in Bot

**Files:**
- Modify: `self_service_copilot/src/self_service_copilot/bot.py`
- Test: `self_service_copilot/tests/test_bot.py`

- [ ] **Step 1: Write the failing bot tests**

```python
def test_handle_mention_ignores_manual_command_for_other_environment(...):
    handle_mention_event(
        event={"text": "<@U123> au get_pod_status payments api-123", "ts": "1", "channel": "C1", "user": "U1"},
        say=say,
        config=config_for(environment="jp", cluster="jp-main"),
        bot_user_id="U123",
        runner=runner,
        limiter=limiter,
    )

    say.assert_not_called()
    runner.run.assert_not_called()


def test_handle_mention_ignores_prometheus_alert_for_other_cluster(...):
    handle_mention_event(
        event={"text": "AlertSource: prometheus\nCluster: au-main\nSeverity: warning", "ts": "1", "channel": "C1", "user": "U1"},
        say=say,
        config=config_for(environment="jp", cluster="jp-main"),
        bot_user_id="U123",
        runner=runner,
        limiter=limiter,
    )

    say.assert_not_called()
    runner.run.assert_not_called()
```

- [ ] **Step 2: Run bot tests to verify failure**

Run: `cd /Users/genewang/Project/genecywang/devops-standards && self_service_copilot/.venv/bin/python -m pytest self_service_copilot/tests/test_bot.py -q`

Expected: FAIL because bot still parses or replies instead of ignoring

- [ ] **Step 3: Implement ownership gate in `bot.py`**

```python
decision = decide_ownership(
    text=text,
    bot_user_id=bot_user_id,
    supported_tools=config.supported_tools,
    my_environment=config.environment,
    my_cluster=config.cluster,
)
logger.info(
    "ownership decision actor=%s channel=%s source_type=%s target_environment=%s target_cluster=%s my_environment=%s my_cluster=%s decision=%s reason=%s",
    actor_id,
    channel_id,
    decision.source_type,
    decision.target_environment,
    decision.target_cluster,
    config.environment,
    config.cluster,
    decision.decision,
    decision.reason,
)
if decision.decision == "ignored":
    return
```

Implementation notes:
- Run the ownership gate after channel allowlist and rate limit, but before existing parse / dispatch.
- Preserve existing parse / dispatch flow for handled manual commands.
- For Prometheus alerts, ownership gate should only filter; no auto-investigation yet.

- [ ] **Step 4: Run bot tests to verify pass**

Run: `cd /Users/genewang/Project/genecywang/devops-standards && self_service_copilot/.venv/bin/python -m pytest self_service_copilot/tests/test_bot.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add self_service_copilot/src/self_service_copilot/bot.py self_service_copilot/tests/test_bot.py
git commit -m "feat: gate slack handling by bot ownership"
```

### Task 4: Document Shared-Channel Rules

**Files:**
- Modify: `self_service_copilot/README.md`

- [ ] **Step 1: Add documentation for ownership behavior**

```md
## Ownership Gate

Each deployed bot instance handles only messages that belong to its own identity:

- Manual commands must use `@copilot <environment> <tool> <namespace> <resource_name>`
- Prometheus alerts are matched by `Cluster:` first
- Messages for another environment or cluster are ignored without a Slack reply

Bot identity comes from:

- `COPILOT_ENVIRONMENT`
- `COPILOT_CLUSTER`
```

- [ ] **Step 2: Verify wording matches implementation**

Run: `rg -n "Ownership Gate|COPILOT_ENVIRONMENT|COPILOT_CLUSTER" self_service_copilot/README.md`

Expected: the new section is present once and uses the same field names as code

- [ ] **Step 3: Commit**

```bash
git add self_service_copilot/README.md
git commit -m "docs: describe copilot ownership gate"
```

### Task 5: Run Focused Verification

**Files:**
- Test: `self_service_copilot/tests/test_config.py`
- Test: `self_service_copilot/tests/test_ownership.py`
- Test: `self_service_copilot/tests/test_bot.py`
- Test: `self_service_copilot/tests/test_parser.py`
- Test: `self_service_copilot/tests/test_dispatcher.py`

- [ ] **Step 1: Run focused self_service_copilot tests**

Run: `cd /Users/genewang/Project/genecywang/devops-standards && self_service_copilot/.venv/bin/python -m pytest self_service_copilot/tests/test_config.py self_service_copilot/tests/test_ownership.py self_service_copilot/tests/test_bot.py self_service_copilot/tests/test_parser.py self_service_copilot/tests/test_dispatcher.py -q`

Expected: PASS

- [ ] **Step 2: Perform local manual-command ownership smoke check**

Run:

```bash
cd /Users/genewang/Project/genecywang/devops-standards/self_service_copilot
.venv/bin/python -c 'from self_service_copilot.ownership import decide_ownership; print(decide_ownership(text="<@U123> jp get_pod_status payments api-123", bot_user_id="U123", supported_tools=frozenset({"get_pod_status"}), my_environment="jp", my_cluster="jp-main"))'
```

Expected: `decision='handled'` and `reason='environment_match'`

- [ ] **Step 3: Perform local Prometheus-alert ownership smoke check**

Run:

```bash
cd /Users/genewang/Project/genecywang/devops-standards/self_service_copilot
.venv/bin/python -c 'from self_service_copilot.ownership import decide_ownership; print(decide_ownership(text="AlertSource: prometheus\nCluster: jp-main\nSeverity: warning", bot_user_id="U123", supported_tools=frozenset({"get_pod_status"}), my_environment="jp", my_cluster="jp-main"))'
```

Expected: `decision='handled'` and `reason='cluster_match'`

- [ ] **Step 4: Commit final verification state**

```bash
git add self_service_copilot
git commit -m "test: verify ownership gate behavior"
```

## Self-Review

- Spec coverage:
  - Bot identity source is covered in Task 1.
  - Manual command ownership is covered in Tasks 2 and 3.
  - Prometheus alert cluster-first routing is covered in Tasks 2 and 3.
  - Shared-channel docs are covered in Task 4.
- Placeholder scan:
  - No `TODO`, `TBD`, or deferred implementation markers remain.
- Type consistency:
  - `CopilotConfig.environment` and `CopilotConfig.cluster` remain the identity fields.
  - `OwnershipDecision` is introduced once and reused consistently.
