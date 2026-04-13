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


def test_sliding_window_allows_until_limit() -> None:
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(now_fn=clock.now)
    rule = RateLimitRule(limit=2, window_seconds=60)

    assert limiter.allow("user:U1", rule) is True
    assert limiter.allow("user:U1", rule) is True
    assert limiter.allow("user:U1", rule) is False


def test_sliding_window_recovers_after_window_passes() -> None:
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(now_fn=clock.now)
    rule = RateLimitRule(limit=1, window_seconds=60)

    assert limiter.allow("user:U1", rule) is True
    assert limiter.allow("user:U1", rule) is False
    clock.advance(61)
    assert limiter.allow("user:U1", rule) is True


def test_copilot_rate_limiter_raises_when_user_limit_exceeded() -> None:
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


def test_copilot_rate_limiter_raises_when_channel_limit_exceeded() -> None:
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
