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
    assist_mode: str = "off"
    provider: str = "stub"
    assist_provider: str = "stub"
    assist_prompt_version: str = "analysis-v1"
    assist_output_schema_version: str = "v1"
    assist_timeout_seconds: float = 10.0
    assist_max_input_chars: int = 4000
    assist_max_output_tokens: int = 500
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
            assist_mode=os.environ.get("OPENCLAW_READONLY_ASSIST_MODE", "off"),
            provider=os.environ.get("INVESTIGATION_PROVIDER", "stub"),
            assist_provider=os.environ.get("OPENCLAW_READONLY_ASSIST_PROVIDER", "stub"),
            assist_prompt_version=os.environ.get(
                "OPENCLAW_READONLY_ASSIST_PROMPT_VERSION",
                "analysis-v1",
            ),
            assist_output_schema_version=os.environ.get(
                "OPENCLAW_READONLY_ASSIST_OUTPUT_SCHEMA_VERSION",
                "v1",
            ),
            assist_timeout_seconds=float(
                os.environ.get("OPENCLAW_READONLY_ASSIST_TIMEOUT_SECONDS", "10")
            ),
            assist_max_input_chars=int(
                os.environ.get("OPENCLAW_READONLY_ASSIST_MAX_INPUT_CHARS", "4000")
            ),
            assist_max_output_tokens=int(
                os.environ.get("OPENCLAW_READONLY_ASSIST_MAX_OUTPUT_TOKENS", "500")
            ),
            allowed_clusters=_split(os.environ.get("ALLOWED_CLUSTERS", "")),
            allowed_namespaces=_split(os.environ.get("ALLOWED_NAMESPACES", "")),
            prometheus_base_url=os.environ.get("OPENCLAW_PROMETHEUS_BASE_URL"),
        )
