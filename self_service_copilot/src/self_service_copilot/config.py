from __future__ import annotations

import os
from dataclasses import dataclass

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

    @classmethod
    def from_env(cls) -> CopilotConfig:
        cluster = os.environ["COPILOT_CLUSTER"]
        environment = os.environ["COPILOT_ENVIRONMENT"]
        allowed_clusters = {s.strip() for s in os.environ["COPILOT_ALLOWED_CLUSTERS"].split(",")}
        allowed_namespaces = {s.strip() for s in os.environ["COPILOT_ALLOWED_NAMESPACES"].split(",")}
        provider = os.environ.get("COPILOT_PROVIDER", "fake")
        return cls(
            cluster=cluster,
            environment=environment,
            allowed_clusters=allowed_clusters,
            allowed_namespaces=allowed_namespaces,
            supported_tools=frozenset({"get_pod_status", "get_pod_events"}),
            default_budget=ExecutionBudget(
                max_steps=2,
                max_tool_calls=1,
                max_duration_seconds=15,
                max_output_tokens=512,
            ),
            provider=provider,
        )
