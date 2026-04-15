from self_service_copilot.ownership import OwnershipDecision, decide_ownership


BOT_ID = "U123"
SUPPORTED = frozenset({"get_pod_status"})


def test_manual_command_matches_same_environment() -> None:
    decision = decide_ownership(
        text=f"<@{BOT_ID}> jp get_pod_status payments api-123",
        bot_user_id=BOT_ID,
        supported_tools=SUPPORTED,
        my_environment="jp",
    )

    assert decision == OwnershipDecision(
        source_type="manual_command",
        decision="handled",
        reason="environment_match",
        target_environment="jp",
    )


def test_manual_command_without_environment_uses_default_path() -> None:
    decision = decide_ownership(
        text=f"<@{BOT_ID}> get_pod_status payments api-123",
        bot_user_id=BOT_ID,
        supported_tools=SUPPORTED,
        my_environment="jp",
    )

    assert decision == OwnershipDecision(
        source_type="manual_command",
        decision="handled",
        reason="default_environment_path",
    )


def test_manual_command_for_other_environment_is_ignored() -> None:
    decision = decide_ownership(
        text=f"<@{BOT_ID}> au get_pod_status payments api-123",
        bot_user_id=BOT_ID,
        supported_tools=SUPPORTED,
        my_environment="jp",
    )

    assert decision == OwnershipDecision(
        source_type="manual_command",
        decision="ignored",
        reason="not_my_environment",
        target_environment="au",
    )


def test_unrelated_text_is_unroutable() -> None:
    decision = decide_ownership(
        text="just a random slack message",
        bot_user_id=BOT_ID,
        supported_tools=SUPPORTED,
        my_environment="jp",
    )

    assert decision == OwnershipDecision(
        source_type="unknown",
        decision="ignored",
        reason="unroutable",
    )


def test_malformed_manual_command_defers_to_parse_handling() -> None:
    decision = decide_ownership(
        text=f"<@{BOT_ID}> get_pod_status payments",
        bot_user_id=BOT_ID,
        supported_tools=SUPPORTED,
        my_environment="jp",
    )

    assert decision == OwnershipDecision(
        source_type="manual_command",
        decision="handled",
        reason="parse_required",
    )
