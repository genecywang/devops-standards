from __future__ import annotations

import os
from dataclasses import dataclass, field

from openclaw_foundation.models.requests import ExecutionBudget


@dataclass
class CopilotConfig:
    cluster: str
    environment: str
    allowed_clusters: set[str]
    allowed_namespaces: set[str]
    supported_tools: frozenset[str]
    default_budget: ExecutionBudget
    provider: str  # "fake" | "real"
    prometheus_base_url: str | None = None
    allowed_channel_ids: set[str] = field(default_factory=set)

    @classmethod
    def from_env(cls) -> CopilotConfig:
        cluster = os.environ["COPILOT_CLUSTER"]
        environment = os.environ["COPILOT_ENVIRONMENT"]
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
            allowed_clusters=allowed_clusters,
            allowed_namespaces=allowed_namespaces,
            prometheus_base_url=prometheus_base_url,
            allowed_channel_ids=allowed_channel_ids,
            supported_tools=frozenset(
                {
                    "get_pod_status",
                    "get_pod_events",
                    "get_deployment_status",
                    "get_pod_runtime",
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
