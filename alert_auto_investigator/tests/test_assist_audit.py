from alert_auto_investigator.assist.audit import AnalysisAuditEvent, build_response_digest


def test_build_response_digest_hashes_redacted_canonical_json() -> None:
    digest = build_response_digest(
        {
            "summary": "healthy",
            "caveats": ["token=[REDACTED]"],
        }
    )

    assert digest == "af273de041d150821dcaf9ca48a511c412df8245f520c391de49f99e50f1e1cb"


def test_build_response_digest_is_independent_of_input_key_order() -> None:
    left = build_response_digest(
        {
            "summary": "healthy",
            "caveats": ["token=[REDACTED]"],
        }
    )
    right = build_response_digest(
        {
            "caveats": ["token=[REDACTED]"],
            "summary": "healthy",
        }
    )

    assert left == right


def test_analysis_audit_event_captures_required_fields() -> None:
    event = AnalysisAuditEvent(
        request_id="req-001",
        alert_key="cloudwatch_alarm:123:ap-east-2:test",
        resource_type="elasticache_cluster",
        resource_name="dev-redis-001",
        tool_name="get_elasticache_cluster_status",
        provider="anthropic",
        model="claude-sonnet",
        prompt_version="analysis-v1",
        analysis_mode="shadow",
        latency_ms=80,
        input_tokens=220,
        output_tokens=110,
        analysis_result_state="success",
        response_digest="a" * 64,
    )

    assert event.provider == "anthropic"
    assert event.analysis_result_state == "success"
    assert event.response_digest == "a" * 64
