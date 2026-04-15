from dataclasses import dataclass
from enum import Enum


class ControlAction(str, Enum):
    INVESTIGATE = "investigate"
    SKIP = "skip"
    SUMMARIZE_ONLY = "summarize_only"


@dataclass(frozen=True)
class ControlDecision:
    action: ControlAction
    reason: str
