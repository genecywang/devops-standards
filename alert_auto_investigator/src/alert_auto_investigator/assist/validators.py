from __future__ import annotations

import json

from alert_auto_investigator.assist.errors import AnalysisRedactionBlockedError


def ensure_analysis_payload_allowed(
    response_redaction_applied: bool,
    payload: dict[str, object],
    max_input_chars: int,
) -> None:
    if not response_redaction_applied:
        raise AnalysisRedactionBlockedError(
            "analysis payload blocked: investigation output was not redacted"
        )

    canonical_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    if len(canonical_payload) > max_input_chars:
        raise AnalysisRedactionBlockedError(
            f"analysis payload blocked: payload size {len(canonical_payload)} exceeds "
            f"input ceiling {max_input_chars}"
        )
