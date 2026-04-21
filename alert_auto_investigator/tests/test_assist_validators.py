from alert_auto_investigator.assist.errors import AnalysisRedactionBlockedError
from alert_auto_investigator.assist.validators import ensure_analysis_payload_allowed


def test_ensure_analysis_payload_allowed_accepts_redacted_payload() -> None:
    payload = {
        "alert": {"alert_key": "alert-1"},
        "investigation": {"summary": "ok"},
    }

    ensure_analysis_payload_allowed(True, payload, max_input_chars=4000)


def test_ensure_analysis_payload_allowed_blocks_unredacted_payload() -> None:
    payload = {
        "alert": {"alert_key": "alert-1"},
        "investigation": {"summary": "ok"},
    }

    try:
        ensure_analysis_payload_allowed(False, payload, max_input_chars=4000)
    except AnalysisRedactionBlockedError as exc:
        assert "redacted" in str(exc)
    else:
        raise AssertionError("AnalysisRedactionBlockedError was not raised")


def test_ensure_analysis_payload_allowed_blocks_oversized_payload() -> None:
    payload = {
        "alert": {"alert_key": "alert-1"},
        "investigation": {"summary": "x" * 4001},
    }

    try:
        ensure_analysis_payload_allowed(True, payload, max_input_chars=4000)
    except AnalysisRedactionBlockedError as exc:
        assert "payload" in str(exc)
    else:
        raise AssertionError("AnalysisRedactionBlockedError was not raised")
