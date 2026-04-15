from alert_auto_investigator.control.store import AlertStateStore
from alert_auto_investigator.models.control_decision import ControlAction, ControlDecision
from alert_auto_investigator.models.control_policy import ControlPolicy
from alert_auto_investigator.models.normalized_alert_event import NormalizedAlertEvent


class ControlPipeline:
    """Deterministic gate between alert ingestion and OpenClaw investigation.

    Checks run in priority order; the first matching check short-circuits
    the rest. No investigation is ever triggered for resolved or unknown events.

    Flap detection (rapid fire/resolve cycling) is not yet implemented and
    is tracked as a future enhancement.
    """

    def __init__(self, policy: ControlPolicy, store: AlertStateStore) -> None:
        self._policy = policy
        self._store = store

    def evaluate(self, event: NormalizedAlertEvent) -> ControlDecision:
        # 1. Fail-close: without alert_key dedup and cooldown cannot work
        if not event.alert_key:
            return ControlDecision(ControlAction.SKIP, "missing alert_key")

        # 2. Resolved / unknown events are never investigated
        if event.status == "resolved":
            return ControlDecision(ControlAction.SKIP, "status is resolved")
        if event.status == "unknown":
            return ControlDecision(ControlAction.SKIP, "status is unknown")

        # 3. Ownership: only process events that belong to this instance
        if event.environment not in self._policy.owned_environments:
            return ControlDecision(
                ControlAction.SKIP,
                f"environment {event.environment!r} is not owned",
            )

        # 4. Denylist: explicit exclusions take priority over allowlist
        if event.alert_name in self._policy.investigate_denylist:
            return ControlDecision(
                ControlAction.SKIP,
                f"alert_name {event.alert_name!r} is in denylist",
            )

        # 5. Allowlist: if non-empty, only listed alert_names are investigated
        if self._policy.investigate_allowlist and event.alert_name not in self._policy.investigate_allowlist:
            return ControlDecision(
                ControlAction.SKIP,
                f"alert_name {event.alert_name!r} is not in allowlist",
            )

        # 6. Cooldown / dedup: same alert investigated too recently
        if self._store.was_investigated_within(event.alert_key, self._policy.cooldown_seconds):
            return ControlDecision(
                ControlAction.SKIP,
                f"alert_key {event.alert_key!r} is in cooldown",
            )

        # 7. Rate limit: global cap on investigations per time window
        count = self._store.count_recent_investigations(self._policy.rate_limit_window_seconds)
        if count >= self._policy.rate_limit_count:
            return ControlDecision(
                ControlAction.SKIP,
                f"rate limit exceeded ({count}/{self._policy.rate_limit_count} per window)",
            )

        return ControlDecision(ControlAction.INVESTIGATE, "all checks passed")

    def record_investigation(self, event: NormalizedAlertEvent) -> None:
        """Call after an investigation is dispatched to update cooldown/rate-limit state."""
        self._store.record_investigation(event.alert_key)
