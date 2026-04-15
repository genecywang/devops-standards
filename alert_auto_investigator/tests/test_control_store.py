from alert_auto_investigator.control.store import InMemoryAlertStateStore


def test_fresh_store_returns_false_for_unknown_key() -> None:
    store = InMemoryAlertStateStore()

    assert store.was_investigated_within("some-alert-key", seconds=3600) is False


def test_was_investigated_within_returns_true_after_recording() -> None:
    store = InMemoryAlertStateStore()
    store.record_investigation("alert-key-1")

    assert store.was_investigated_within("alert-key-1", seconds=3600) is True


def test_was_investigated_within_returns_false_for_unrecorded_key() -> None:
    store = InMemoryAlertStateStore()
    store.record_investigation("alert-key-1")

    assert store.was_investigated_within("alert-key-2", seconds=3600) is False


def test_was_investigated_within_uses_per_key_timestamp() -> None:
    store = InMemoryAlertStateStore()
    store.record_investigation("alert-key-a")
    store.record_investigation("alert-key-b")

    assert store.was_investigated_within("alert-key-a", seconds=3600) is True
    assert store.was_investigated_within("alert-key-b", seconds=3600) is True


def test_count_recent_investigations_returns_zero_for_empty_store() -> None:
    store = InMemoryAlertStateStore()

    assert store.count_recent_investigations(window_seconds=3600) == 0


def test_count_recent_investigations_reflects_recorded_entries() -> None:
    store = InMemoryAlertStateStore()
    store.record_investigation("key-1")
    store.record_investigation("key-2")
    store.record_investigation("key-3")

    assert store.count_recent_investigations(window_seconds=3600) == 3


def test_count_recent_investigations_zero_window_excludes_all() -> None:
    store = InMemoryAlertStateStore()
    store.record_investigation("key-1")

    # A window of 0 seconds means nothing is "recent"; all timestamps are in the past
    assert store.count_recent_investigations(window_seconds=0) == 0


def test_record_investigation_overwrites_previous_timestamp() -> None:
    store = InMemoryAlertStateStore()
    store.record_investigation("key-1")
    store.record_investigation("key-1")

    # Both recordings should appear in history but only the latest timestamp is in _last_seen
    assert store.count_recent_investigations(window_seconds=3600) == 2
    assert store.was_investigated_within("key-1", seconds=3600) is True
