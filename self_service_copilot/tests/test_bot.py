from self_service_copilot.bot import should_handle_channel


def test_should_handle_channel_returns_false_for_disallowed_channel() -> None:
    assert should_handle_channel("C999", {"C123", "C456"}) is False


def test_should_handle_channel_returns_true_for_allowed_channel() -> None:
    assert should_handle_channel("C123", {"C123", "C456"}) is True


def test_should_handle_channel_returns_true_when_allowlist_is_empty() -> None:
    assert should_handle_channel("C999", set()) is True
