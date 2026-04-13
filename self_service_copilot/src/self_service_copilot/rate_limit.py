from __future__ import annotations

import time
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
        self._now_fn = now_fn or time.time
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
