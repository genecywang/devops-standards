import time
from typing import Protocol, runtime_checkable


@runtime_checkable
class AlertStateStore(Protocol):
    """Read/write store for alert investigation state.

    Used by ControlPipeline to enforce cooldown and rate limiting.
    Implementations must be safe for single-threaded use; concurrent
    access requires external locking.
    """

    def was_investigated_within(self, alert_key: str, seconds: float) -> bool:
        """Return True if alert_key was investigated less than `seconds` ago."""
        ...

    def record_investigation(self, alert_key: str) -> None:
        """Record that alert_key was investigated right now."""
        ...

    def count_recent_investigations(self, window_seconds: float) -> int:
        """Return the number of investigations recorded within the last `window_seconds`."""
        ...


class InMemoryAlertStateStore:
    """Non-persistent in-process implementation of AlertStateStore.

    Suitable for local testing and single-process deployments.
    State is lost on restart; does not survive pod restarts.
    """

    def __init__(self) -> None:
        self._last_seen: dict[str, float] = {}
        self._history: list[float] = []

    def was_investigated_within(self, alert_key: str, seconds: float) -> bool:
        last = self._last_seen.get(alert_key)
        if last is None:
            return False
        return (time.monotonic() - last) < seconds

    def record_investigation(self, alert_key: str) -> None:
        now = time.monotonic()
        self._last_seen[alert_key] = now
        self._history.append(now)

    def count_recent_investigations(self, window_seconds: float) -> int:
        cutoff = time.monotonic() - window_seconds
        return sum(1 for t in self._history if t >= cutoff)
