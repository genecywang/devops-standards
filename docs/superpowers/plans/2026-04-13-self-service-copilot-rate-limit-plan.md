# Self-Service Copilot Rate Limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為 `self_service_copilot` 增加 in-memory sliding-window rate limit，對 Slack mention 同時做 `per-user` 與 `per-channel` 保護。

**Architecture:** 新增 `rate_limit.py` 來封裝 sliding-window limiter 與 copilot-specific wrapper；`config.py` 讀取 rate limit env defaults；`bot.py` 在 channel allowlist 後、parse 前做限流檢查，超限時回固定 deny 訊息，不進 dispatcher / runner。

**Tech Stack:** Python 3.11, `collections.deque`, pytest, Slack Socket Mode bot

---

## File Structure

| 狀態 | 路徑 | 責任 |
|------|------|------|
| 新增 | `self_service_copilot/src/self_service_copilot/rate_limit.py` | sliding-window limiter 與 `CopilotRateLimiter` |
| 修改 | `self_service_copilot/src/self_service_copilot/config.py` | rate limit env parsing 與 config fields |
| 修改 | `self_service_copilot/src/self_service_copilot/bot.py` | integrate rate limit check |
| 新增 | `self_service_copilot/tests/test_rate_limit.py` | limiter unit tests |
| 修改 | `self_service_copilot/tests/test_config.py` | config env mapping tests |
| 修改 | `self_service_copilot/tests/test_bot.py` | bot-level deny behavior tests |

---

## Task 1: Add `rate_limit.py` with sliding-window limiter

**Files:**
- Create: `self_service_copilot/src/self_service_copilot/rate_limit.py`
- Test: `self_service_copilot/tests/test_rate_limit.py`

- [ ] **Step 1: Write failing tests for limiter behavior**

Create `self_service_copilot/tests/test_rate_limit.py` with:

```python
from self_service_copilot.rate_limit import (
    CopilotRateLimiter,
    RateLimitExceededError,
    RateLimitRule,
    SlidingWindowRateLimiter,
)


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.value = start

    def now(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def test_sliding_window_allows_until_limit():
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(now_fn=clock.now)
    rule = RateLimitRule(limit=2, window_seconds=60)

    assert limiter.allow("user:U1", rule) is True
    assert limiter.allow("user:U1", rule) is True
    assert limiter.allow("user:U1", rule) is False


def test_sliding_window_recovers_after_window_passes():
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(now_fn=clock.now)
    rule = RateLimitRule(limit=1, window_seconds=60)

    assert limiter.allow("user:U1", rule) is True
    assert limiter.allow("user:U1", rule) is False
    clock.advance(61)
    assert limiter.allow("user:U1", rule) is True


def test_copilot_rate_limiter_raises_when_user_limit_exceeded():
    clock = FakeClock()
    limiter = CopilotRateLimiter(
        user_rule=RateLimitRule(limit=1, window_seconds=60),
        channel_rule=RateLimitRule(limit=10, window_seconds=60),
        now_fn=clock.now,
    )

    limiter.check(actor_id="U1", channel_id="C1")

    try:
        limiter.check(actor_id="U1", channel_id="C1")
        assert False, "expected RateLimitExceededError"
    except RateLimitExceededError:
        pass


def test_copilot_rate_limiter_raises_when_channel_limit_exceeded():
    clock = FakeClock()
    limiter = CopilotRateLimiter(
        user_rule=RateLimitRule(limit=10, window_seconds=60),
        channel_rule=RateLimitRule(limit=1, window_seconds=60),
        now_fn=clock.now,
    )

    limiter.check(actor_id="U1", channel_id="C1")

    try:
        limiter.check(actor_id="U2", channel_id="C1")
        assert False, "expected RateLimitExceededError"
    except RateLimitExceededError:
        pass
```

- [ ] **Step 2: Verify tests fail**

Run:

```bash
cd self_service_copilot
.venv/bin/python -m pytest tests/test_rate_limit.py -q
```

Expected:

- `ModuleNotFoundError` for `self_service_copilot.rate_limit`

- [ ] **Step 3: Implement minimal limiter**

Create `self_service_copilot/src/self_service_copilot/rate_limit.py`:

```python
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RateLimitRule:
    limit: int
    window_seconds: int


class RateLimitExceededError(ValueError):
    pass


class SlidingWindowRateLimiter:
    def __init__(self, now_fn: Callable[[], float] | None = None) -> None:
        self._now_fn = now_fn or __import__("time").time
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, rule: RateLimitRule) -> bool:
        now = self._now_fn()
        bucket = self._buckets[key]
        cutoff = now - rule.window_seconds

        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= rule.limit:
            return False

        bucket.append(now)
        return True


class CopilotRateLimiter:
    def __init__(
        self,
        user_rule: RateLimitRule,
        channel_rule: RateLimitRule,
        now_fn: Callable[[], float] | None = None,
    ) -> None:
        self._limiter = SlidingWindowRateLimiter(now_fn=now_fn)
        self._user_rule = user_rule
        self._channel_rule = channel_rule

    def check(self, actor_id: str, channel_id: str) -> None:
        if not self._limiter.allow(f"user:{actor_id}", self._user_rule):
            raise RateLimitExceededError("rate limit exceeded")

        if not self._limiter.allow(f"channel:{channel_id}", self._channel_rule):
            raise RateLimitExceededError("rate limit exceeded")
```

- [ ] **Step 4: Verify tests pass**

Run:

```bash
cd self_service_copilot
.venv/bin/python -m pytest tests/test_rate_limit.py -q
```

Expected:

- all tests pass

- [ ] **Step 5: Commit**

```bash
git add self_service_copilot/src/self_service_copilot/rate_limit.py \
        self_service_copilot/tests/test_rate_limit.py
git commit -m "feat: add sliding window rate limiter for copilot"
```

---

## Task 2: Add rate limit config to `CopilotConfig`

**Files:**
- Modify: `self_service_copilot/src/self_service_copilot/config.py`
- Test: `self_service_copilot/tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

Append to `self_service_copilot/tests/test_config.py`:

```python
def test_from_env_uses_default_rate_limits(monkeypatch):
    monkeypatch.delenv("COPILOT_USER_RATE_LIMIT_COUNT", raising=False)
    monkeypatch.delenv("COPILOT_USER_RATE_LIMIT_WINDOW_SECONDS", raising=False)
    monkeypatch.delenv("COPILOT_CHANNEL_RATE_LIMIT_COUNT", raising=False)
    monkeypatch.delenv("COPILOT_CHANNEL_RATE_LIMIT_WINDOW_SECONDS", raising=False)

    config = CopilotConfig.from_env()

    assert config.user_rate_limit_count == 5
    assert config.user_rate_limit_window_seconds == 60
    assert config.channel_rate_limit_count == 20
    assert config.channel_rate_limit_window_seconds == 60


def test_from_env_reads_rate_limit_overrides(monkeypatch):
    monkeypatch.setenv("COPILOT_USER_RATE_LIMIT_COUNT", "7")
    monkeypatch.setenv("COPILOT_USER_RATE_LIMIT_WINDOW_SECONDS", "30")
    monkeypatch.setenv("COPILOT_CHANNEL_RATE_LIMIT_COUNT", "50")
    monkeypatch.setenv("COPILOT_CHANNEL_RATE_LIMIT_WINDOW_SECONDS", "120")

    config = CopilotConfig.from_env()

    assert config.user_rate_limit_count == 7
    assert config.user_rate_limit_window_seconds == 30
    assert config.channel_rate_limit_count == 50
    assert config.channel_rate_limit_window_seconds == 120
```

- [ ] **Step 2: Verify tests fail**

Run:

```bash
cd self_service_copilot
.venv/bin/python -m pytest tests/test_config.py -k "rate_limit" -q
```

Expected:

- `AttributeError` for missing config fields

- [ ] **Step 3: Implement config fields and env parsing**

Update `CopilotConfig` in `self_service_copilot/src/self_service_copilot/config.py` to include:

```python
    user_rate_limit_count: int
    user_rate_limit_window_seconds: int
    channel_rate_limit_count: int
    channel_rate_limit_window_seconds: int
```

And in `from_env()` return:

```python
            user_rate_limit_count=int(os.environ.get("COPILOT_USER_RATE_LIMIT_COUNT", "5")),
            user_rate_limit_window_seconds=int(
                os.environ.get("COPILOT_USER_RATE_LIMIT_WINDOW_SECONDS", "60")
            ),
            channel_rate_limit_count=int(
                os.environ.get("COPILOT_CHANNEL_RATE_LIMIT_COUNT", "20")
            ),
            channel_rate_limit_window_seconds=int(
                os.environ.get("COPILOT_CHANNEL_RATE_LIMIT_WINDOW_SECONDS", "60")
            ),
```

- [ ] **Step 4: Verify config tests pass**

Run:

```bash
cd self_service_copilot
.venv/bin/python -m pytest tests/test_config.py -q
```

Expected:

- all config tests pass

- [ ] **Step 5: Commit**

```bash
git add self_service_copilot/src/self_service_copilot/config.py \
        self_service_copilot/tests/test_config.py
git commit -m "feat: add rate limit settings to copilot config"
```

---

## Task 3: Integrate rate limiting into `bot.py`

**Files:**
- Modify: `self_service_copilot/src/self_service_copilot/bot.py`
- Modify: `self_service_copilot/tests/test_bot.py`

- [ ] **Step 1: Write failing bot tests**

Append to `self_service_copilot/tests/test_bot.py`:

```python
from self_service_copilot.rate_limit import CopilotRateLimiter, RateLimitRule


def test_handle_mention_replies_when_rate_limited(monkeypatch):
    app, say, ack = build_test_harness(monkeypatch)
    limiter = CopilotRateLimiter(
        user_rule=RateLimitRule(limit=0, window_seconds=60),
        channel_rule=RateLimitRule(limit=10, window_seconds=60),
    )

    monkeypatch.setattr("self_service_copilot.bot.build_rate_limiter", lambda config: limiter)

    event = {
        "channel": "C1",
        "user": "U1",
        "text": "<@UBOT> get_pod_status payments payments-api-123",
        "ts": "1710000000.000100",
    }

    app.dispatch(event, ack=ack, say=say, bot_user_id="UBOT")

    assert say.calls == [
        (
            "[denied] rate limit exceeded, please retry later",
            "1710000000.000100",
        )
    ]
```

And a second test:

```python
def test_handle_mention_rate_limit_blocks_before_runner(monkeypatch):
    app, say, ack = build_test_harness(monkeypatch)
    limiter = CopilotRateLimiter(
        user_rule=RateLimitRule(limit=0, window_seconds=60),
        channel_rule=RateLimitRule(limit=10, window_seconds=60),
    )

    runner = RecordingRunner()

    monkeypatch.setattr("self_service_copilot.bot.build_rate_limiter", lambda config: limiter)
    monkeypatch.setattr("self_service_copilot.bot.build_runner", lambda config: runner)

    event = {
        "channel": "C1",
        "user": "U1",
        "text": "<@UBOT> get_pod_status payments payments-api-123",
        "ts": "1710000000.000100",
    }

    app.dispatch(event, ack=ack, say=say, bot_user_id="UBOT")

    assert runner.calls == []
```

- [ ] **Step 2: Verify tests fail**

Run:

```bash
cd self_service_copilot
.venv/bin/python -m pytest tests/test_bot.py -k "rate_limit" -q
```

Expected:

- failure because `build_rate_limiter` does not exist

- [ ] **Step 3: Implement limiter wiring**

In `self_service_copilot/src/self_service_copilot/bot.py`:

1. Add imports:

```python
from self_service_copilot.rate_limit import (
    CopilotRateLimiter,
    RateLimitExceededError,
    RateLimitRule,
)
```

2. Add helper:

```python
def build_rate_limiter(config: CopilotConfig) -> CopilotRateLimiter:
    return CopilotRateLimiter(
        user_rule=RateLimitRule(
            limit=config.user_rate_limit_count,
            window_seconds=config.user_rate_limit_window_seconds,
        ),
        channel_rule=RateLimitRule(
            limit=config.channel_rate_limit_count,
            window_seconds=config.channel_rate_limit_window_seconds,
        ),
    )
```

3. In `main()`, create limiter once:

```python
    limiter = build_rate_limiter(config)
```

4. In mention handler, after channel allowlist check and before parse:

```python
        try:
            limiter.check(actor_id=actor_id, channel_id=channel_id)
        except RateLimitExceededError:
            logger.info(
                "rate limit exceeded for actor=%s channel=%s",
                actor_id,
                channel_id,
            )
            safe_reply(
                say,
                "[denied] rate limit exceeded, please retry later",
                event_ts,
            )
            return
```

- [ ] **Step 4: Verify bot tests pass**

Run:

```bash
cd self_service_copilot
.venv/bin/python -m pytest tests/test_bot.py -q
```

Expected:

- all bot tests pass

- [ ] **Step 5: Commit**

```bash
git add self_service_copilot/src/self_service_copilot/bot.py \
        self_service_copilot/tests/test_bot.py
git commit -m "feat: enforce rate limits in copilot bot"
```

---

## Task 4: Full verification and README env note

**Files:**
- Modify: `self_service_copilot/README.md`

- [ ] **Step 1: Add env notes to README**

Append under runtime env examples:

```md
Optional rate limit env vars:

- `COPILOT_USER_RATE_LIMIT_COUNT` (default: `5`)
- `COPILOT_USER_RATE_LIMIT_WINDOW_SECONDS` (default: `60`)
- `COPILOT_CHANNEL_RATE_LIMIT_COUNT` (default: `20`)
- `COPILOT_CHANNEL_RATE_LIMIT_WINDOW_SECONDS` (default: `60`)
```

- [ ] **Step 2: Verify full copilot test suite**

Run:

```bash
cd self_service_copilot
.venv/bin/python -m pytest tests -q
```

Expected:

- full suite passes

- [ ] **Step 3: Verify foundation suite still green**

Run:

```bash
openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests -q
```

Expected:

- all foundation tests pass

- [ ] **Step 4: Final commit**

```bash
git add self_service_copilot/README.md
git commit -m "docs: add rate limit environment notes"
```
