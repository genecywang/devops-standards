from dataclasses import dataclass, field


@dataclass(frozen=True)
class ControlPolicy:
    # environments this instance owns; events from other environments are skipped
    owned_environments: frozenset[str]
    # if non-empty, only alert_names in this set are investigated
    investigate_allowlist: frozenset[str] = field(default_factory=frozenset)
    # alert_names that are never investigated regardless of other checks
    investigate_denylist: frozenset[str] = field(default_factory=frozenset)
    # minimum seconds between two investigations of the same alert_key
    cooldown_seconds: float = 900.0
    # max number of investigations allowed within the rate-limit window
    rate_limit_count: int = 10
    # duration of the rate-limit window in seconds
    rate_limit_window_seconds: float = 3600.0
