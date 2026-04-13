from dataclasses import dataclass

from openclaw_foundation.models.enums import RequestType


@dataclass(slots=True)
class ExecutionBudget:
    max_steps: int
    max_tool_calls: int
    max_duration_seconds: int
    max_output_tokens: int

    def __post_init__(self) -> None:
        for value in (
            self.max_steps,
            self.max_tool_calls,
            self.max_duration_seconds,
            self.max_output_tokens,
        ):
            if value <= 0:
                raise ValueError("execution budget fields must be positive integers")


@dataclass(slots=True)
class InvestigationRequest:
    request_type: RequestType
    request_id: str
    source_product: str
    scope: dict[str, str]
    input_ref: str
    budget: ExecutionBudget
    tool_name: str = "fake_investigation"
    target: dict[str, str] | None = None
    requested_by: str | None = None

    def __post_init__(self) -> None:
        if self.request_type != RequestType.INVESTIGATION:
            raise ValueError("only investigation requests are supported in the skeleton")
        if not self.request_id:
            raise ValueError("request_id is required")
        if not self.source_product:
            raise ValueError("source_product is required")
        if not self.scope:
            raise ValueError("scope is required")
        if not self.input_ref:
            raise ValueError("input_ref is required")

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "InvestigationRequest":
        budget_payload = payload["budget"]
        if not isinstance(budget_payload, dict):
            raise ValueError("budget must be an object")

        return cls(
            request_type=RequestType(payload["request_type"]),
            request_id=str(payload["request_id"]),
            source_product=str(payload["source_product"]),
            scope=dict(payload["scope"]),
            input_ref=str(payload["input_ref"]),
            budget=ExecutionBudget(
                max_steps=int(budget_payload["max_steps"]),
                max_tool_calls=int(budget_payload["max_tool_calls"]),
                max_duration_seconds=int(budget_payload["max_duration_seconds"]),
                max_output_tokens=int(budget_payload["max_output_tokens"]),
            ),
            tool_name=str(payload.get("tool_name", "fake_investigation")),
            target=dict(payload["target"]) if "target" in payload and payload["target"] is not None else None,
        )
