import logging
import uuid
from dataclasses import dataclass
from typing import Protocol

from alert_auto_investigator.models.normalized_alert_event import NormalizedAlertEvent
from alert_auto_investigator.models.resource_type import InvestigationPolicy, ResourceType, SUPPORT_MATRIX

logger = logging.getLogger(__name__)

DEFAULT_TOOL_ROUTING: dict[str, str] = {
    ResourceType.POD: "get_pod_events",
    ResourceType.DEPLOYMENT: "get_deployment_status",
    ResourceType.JOB: "get_job_status",
}


@dataclass
class InvestigationConfig:
    tool_routing: dict[str, str]
    max_steps: int = 3
    max_tool_calls: int = 2
    max_duration_seconds: int = 30
    max_output_tokens: int = 1024


class InvestigationRequest(Protocol):
    """Structural type accepted by runners; matches openclaw_foundation.models.requests.InvestigationRequest."""

    request_id: str
    tool_name: str
    target: dict[str, str] | None
    scope: dict[str, str]


class InvestigationRunner(Protocol):
    """Structural type for OpenClawRunner; allows injecting fakes in tests."""

    def run(self, request) -> object: ...


class OpenClawDispatcher:
    """Maps a NormalizedAlertEvent to an OpenClaw InvestigationRequest and executes it.

    Returns None when no tool is mapped for the event's resource_type (no investigation).
    Callers are responsible for calling ControlPipeline.record_investigation() after dispatch.
    """

    def __init__(self, runner: InvestigationRunner, config: InvestigationConfig) -> None:
        self._runner = runner
        self._config = config

    def dispatch(
        self,
        event: NormalizedAlertEvent,
        request_id: str | None = None,
    ) -> object | None:
        """Dispatch an investigation for the event.

        Returns the runner's response (CanonicalResponse) or None if
        the event's resource_type has no tool mapping.
        """
        tool_name = self._config.tool_routing.get(event.resource_type)
        if tool_name is None:
            policy = SUPPORT_MATRIX.get(event.resource_type)
            if policy is InvestigationPolicy.SKIP:
                logger.debug(
                    "skip_by_design resource_type=%s alert_key=%s",
                    event.resource_type,
                    event.alert_key,
                )
            elif policy is InvestigationPolicy.NEXT_CANDIDATE:
                logger.info(
                    "next_candidate_not_yet_implemented resource_type=%s alert_key=%s",
                    event.resource_type,
                    event.alert_key,
                )
            elif policy is InvestigationPolicy.INVESTIGATE:
                logger.warning(
                    "supported_but_unrouted resource_type=%s alert_key=%s",
                    event.resource_type,
                    event.alert_key,
                )
            else:
                logger.warning(
                    "unknown_resource_type resource_type=%s alert_key=%s — not in support matrix",
                    event.resource_type,
                    event.alert_key,
                )
            return None

        if request_id is None:
            request_id = str(uuid.uuid4())

        logger.info(
            "dispatching_investigation resource_type=%s tool_name=%s alert_key=%s",
            event.resource_type,
            tool_name,
            event.alert_key,
        )
        request = self._build_request(event, tool_name, request_id)
        return self._runner.run(request)

    def _build_request(
        self,
        event: NormalizedAlertEvent,
        tool_name: str,
        request_id: str,
    ) -> object:
        # Import here to keep openclaw_foundation as an optional dep in tests that stub the runner
        from openclaw_foundation.models.enums import RequestType
        from openclaw_foundation.models.requests import ExecutionBudget, InvestigationRequest

        return InvestigationRequest(
            request_type=RequestType.INVESTIGATION,
            request_id=request_id,
            source_product="alert_auto_investigator",
            scope={
                "environment": event.environment,
                "cluster": event.cluster,
                "region_code": event.region_code,
            },
            input_ref=f"alert:{event.alert_key}",
            budget=ExecutionBudget(
                max_steps=self._config.max_steps,
                max_tool_calls=self._config.max_tool_calls,
                max_duration_seconds=self._config.max_duration_seconds,
                max_output_tokens=self._config.max_output_tokens,
            ),
            tool_name=tool_name,
            target={
                "cluster": event.cluster,
                "namespace": event.namespace,
                "resource_name": event.resource_name,
            },
        )
