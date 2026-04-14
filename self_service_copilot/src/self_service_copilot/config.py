from __future__ import annotations

import os
from dataclasses import dataclass, field

from openclaw_foundation.models.requests import ExecutionBudget


@dataclass
class CopilotConfig:
    # Bot identity is defined by cluster + environment for now.
    cluster: str
    environment: str
    allowed_clusters: set[str]
    allowed_namespaces: set[str]
    supported_tools: frozenset[str]
    default_budget: ExecutionBudget
    provider: str  # "fake" | "real"
    default_environment: str = ""
    environment_clusters: dict[str, str] = field(default_factory=dict)
    prometheus_base_url: str | None = None
    allowed_channel_ids: set[str] = field(default_factory=set)
    user_rate_limit_count: int = 5
    user_rate_limit_window_seconds: int = 60
    channel_rate_limit_count: int = 20
    channel_rate_limit_window_seconds: int = 60

    def __post_init__(self) -> None:
        if not self.default_environment:
            self.default_environment = self.environment
        self.environment_clusters.setdefault(self.default_environment, self.cluster)

    @classmethod
    def from_env(cls) -> CopilotConfig:
        cluster = os.environ["COPILOT_CLUSTER"]
        environment = os.environ["COPILOT_ENVIRONMENT"]
        default_environment = _normalize_default_environment(
            os.environ.get("COPILOT_DEFAULT_ENVIRONMENT"), environment
        )
        environment_clusters_env = os.environ.get("COPILOT_ENVIRONMENT_CLUSTERS", "")
        environment_clusters = _parse_environment_clusters(environment_clusters_env)
        environment_clusters.setdefault(default_environment, cluster)
        allowed_clusters = {s.strip() for s in os.environ["COPILOT_ALLOWED_CLUSTERS"].split(",")}
        allowed_namespaces = {s.strip() for s in os.environ["COPILOT_ALLOWED_NAMESPACES"].split(",")}
        allowed_channel_ids = {
            s.strip()
            for s in os.environ.get("COPILOT_ALLOWED_CHANNEL_IDS", "").split(",")
            if s.strip()
        }
        prometheus_base_url = os.environ.get("OPENCLAW_PROMETHEUS_BASE_URL")
        provider = os.environ.get("COPILOT_PROVIDER", "fake")
        return cls(
            cluster=cluster,
            environment=environment,
            default_environment=default_environment,
            environment_clusters=environment_clusters,
            allowed_clusters=allowed_clusters,
            allowed_namespaces=allowed_namespaces,
            prometheus_base_url=prometheus_base_url,
            allowed_channel_ids=allowed_channel_ids,
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
            supported_tools=frozenset(
                {
                    "get_pod_status",
                    "get_pod_events",
                    "get_deployment_status",
                    "get_pod_runtime",
                    "get_pod_cpu_usage",
                    "get_deployment_restart_rate",
                }
            ),
            default_budget=ExecutionBudget(
                max_steps=2,
                max_tool_calls=1,
                max_duration_seconds=15,
                max_output_tokens=512,
            ),
            provider=provider,
        )


def _parse_environment_clusters(value: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in value.split(","):
        entry = item.strip()
        if not entry:
            continue
        if "=" not in entry:
            raise ValueError(f"Invalid COPILOT_ENVIRONMENT_CLUSTERS entry: {item!r}")
        environment, cluster = entry.split("=", 1)
        environment = environment.strip()
        cluster = cluster.strip()
        if not environment or not cluster:
            raise ValueError(f"Invalid COPILOT_ENVIRONMENT_CLUSTERS entry: {item!r}")
        mapping[environment] = cluster
    return mapping


def _normalize_default_environment(value: str | None, fallback: str) -> str:
    if value is None:
        return fallback
    normalized = value.strip()
    return normalized or fallback
