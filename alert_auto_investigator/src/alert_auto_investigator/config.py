import os
from dataclasses import dataclass


@dataclass
class InvestigatorConfig:
    slack_bot_token: str
    slack_app_token: str
    region_code: str
    fallback_environment: str
    owned_environments: list[str]
    cooldown_seconds: float
    rate_limit_count: int
    rate_limit_window_seconds: float
    investigate_allowlist: list[str]
    investigate_denylist: list[str]
    allowed_channel_ids: list[str] | None = None
    provider: str = "stub"
    allowed_clusters: list[str] | None = None
    allowed_namespaces: list[str] | None = None
    prometheus_base_url: str | None = None

    @classmethod
    def from_env(cls) -> "InvestigatorConfig":
        def _split(val: str) -> list[str]:
            return [v.strip() for v in val.split(",") if v.strip()]

        return cls(
            slack_bot_token=os.environ["SLACK_BOT_TOKEN"],
            slack_app_token=os.environ["SLACK_APP_TOKEN"],
            region_code=os.environ["REGION_CODE"],
            fallback_environment=os.environ["FALLBACK_ENVIRONMENT"],
            owned_environments=_split(os.environ["OWNED_ENVIRONMENTS"]),
            cooldown_seconds=float(os.environ.get("COOLDOWN_SECONDS", "300")),
            rate_limit_count=int(os.environ.get("RATE_LIMIT_COUNT", "10")),
            rate_limit_window_seconds=float(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "3600")),
            investigate_allowlist=_split(os.environ.get("INVESTIGATE_ALLOWLIST", "")),
            investigate_denylist=_split(os.environ.get("INVESTIGATE_DENYLIST", "")),
            allowed_channel_ids=_split(os.environ.get("ALERT_INVESTIGATOR_ALLOWED_CHANNEL_IDS", "")),
            provider=os.environ.get("INVESTIGATION_PROVIDER", "stub"),
            allowed_clusters=_split(os.environ.get("ALLOWED_CLUSTERS", "")),
            allowed_namespaces=_split(os.environ.get("ALLOWED_NAMESPACES", "")),
            prometheus_base_url=os.environ.get("OPENCLAW_PROMETHEUS_BASE_URL"),
        )
