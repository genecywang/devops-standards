from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


def build_response_digest(payload: dict[str, object]) -> str:
    canonical_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class AnalysisAuditEvent:
    request_id: str
    alert_key: str
    resource_type: str
    resource_name: str
    tool_name: str
    provider: str
    model: str
    prompt_version: str
    analysis_mode: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    analysis_result_state: str
    response_digest: str
