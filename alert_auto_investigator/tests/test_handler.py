"""Tests for alert_auto_investigator.service.handler.

Covers:
- _extract_texts: attachment-first, fallback to event text
- _reply_ts: thread_ts preference
- handle_message: bot guards, silent skip, parse routing,
  control pipeline gating, record-after-dispatch, Slack reply targeting
"""

from unittest.mock import ANY, MagicMock

from alert_auto_investigator.config import InvestigatorConfig
from alert_auto_investigator.control.pipeline import ControlPipeline
from alert_auto_investigator.control.store import InMemoryAlertStateStore
from alert_auto_investigator.models.control_policy import ControlPolicy
from alert_auto_investigator.service.handler import _extract_texts, _reply_ts, handle_message

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

_ALERTMANAGER_TEXT = """\
HostOutOfMemory on ip-172-16-52-233.ap-east-1.compute.internal
Severity: warning
Summary: Host out of memory (instance ip-172-16-52-233.ap-east-1.compute.internal)

--- Structured Alert ---
AlertSource: prometheus
Environment: unknown
Cluster: test-cluster
Severity: warning
Status: firing
AlertName: HostOutOfMemory
ResourceType: host
ResourceName: ip-172-16-52-233.ap-east-1.compute.internal
Namespace: -
Summary: Host out of memory
Description: Node memory > 85%

RawLabels:
- alertname=HostOutOfMemory
- cluster=test-cluster
- severity=warning
"""

_CLOUDWATCH_TEXT = """\
:fire: [*FIRING*] some human wording

--- Structured Alert ---
schema_version: v1
source: cloudwatch_alarm
status: ALARM
alert_name: HighCPUUtilization
account_id: 123456789012
region_code: ap-east-1
environment: dev
event_time: 2024-01-01T00:00:00Z
alert_key: cloudwatch_alarm:123456789012:ap-east-1:HighCPUUtilization
resource_type: ec2_instance
resource_name: i-1234567890abcdef0
"""


def _make_config(
    allowlist: list[str] | None = None,
    denylist: list[str] | None = None,
    cooldown_seconds: float = 0.0,
    allowed_channel_ids: list[str] | None = None,
) -> InvestigatorConfig:
    return InvestigatorConfig(
        slack_bot_token="xoxb-test",
        slack_app_token="xapp-test",
        region_code="ap-east-1",
        fallback_environment="dev",
        owned_environments=["dev"],
        cooldown_seconds=cooldown_seconds,
        rate_limit_count=100,
        rate_limit_window_seconds=60.0,
        investigate_allowlist=allowlist if allowlist is not None else [],
        investigate_denylist=denylist if denylist is not None else [],
        allowed_channel_ids=allowed_channel_ids if allowed_channel_ids is not None else [],
    )


def _make_pipeline(config: InvestigatorConfig) -> ControlPipeline:
    policy = ControlPolicy(
        owned_environments=frozenset(config.owned_environments),
        investigate_allowlist=frozenset(config.investigate_allowlist),
        investigate_denylist=frozenset(config.investigate_denylist),
        cooldown_seconds=config.cooldown_seconds,
        rate_limit_count=config.rate_limit_count,
        rate_limit_window_seconds=config.rate_limit_window_seconds,
    )
    return ControlPipeline(policy, InMemoryAlertStateStore())


def _make_event(
    text: str = "",
    attachments: list[dict] | None = None,
    bot_id: str | None = None,
    subtype: str | None = None,
    ts: str = "111.000",
    thread_ts: str | None = None,
) -> dict:
    event: dict = {"ts": ts, "channel": "C123", "text": text}
    if attachments is not None:
        event["attachments"] = attachments
    if bot_id is not None:
        event["bot_id"] = bot_id
    if subtype is not None:
        event["subtype"] = subtype
    if thread_ts is not None:
        event["thread_ts"] = thread_ts
    return event


# ---------------------------------------------------------------------------
# _extract_texts
# ---------------------------------------------------------------------------


class TestExtractTexts:
    def test_returns_attachment_text(self) -> None:
        assert _extract_texts({"attachments": [{"text": "hello"}]}) == ["hello"]

    def test_returns_multiple_attachment_texts(self) -> None:
        event = {"attachments": [{"text": "a"}, {"text": "b"}]}
        assert _extract_texts(event) == ["a", "b"]

    def test_skips_empty_attachment_text(self) -> None:
        event = {"attachments": [{"text": ""}, {"text": "b"}]}
        assert _extract_texts(event) == ["b"]

    def test_falls_back_to_event_text_when_no_attachments(self) -> None:
        assert _extract_texts({"text": "hello"}) == ["hello"]

    def test_no_fallback_when_attachments_present(self) -> None:
        event = {"text": "ignored", "attachments": [{"text": "used"}]}
        assert _extract_texts(event) == ["used"]

    def test_empty_list_when_nothing_available(self) -> None:
        assert _extract_texts({}) == []


# ---------------------------------------------------------------------------
# _reply_ts
# ---------------------------------------------------------------------------


class TestReplyTs:
    def test_uses_thread_ts_when_present(self) -> None:
        assert _reply_ts({"ts": "111", "thread_ts": "222"}) == "222"

    def test_falls_back_to_ts(self) -> None:
        assert _reply_ts({"ts": "111"}) == "111"


# ---------------------------------------------------------------------------
# handle_message — bot guards
# ---------------------------------------------------------------------------


OWN_BOT_ID = "B_OWN_BOT"
ALERTMANAGER_BOT_ID = "B_ALERTMANAGER"
CLOUDWATCH_BOT_ID = "B_CLOUDWATCH"


class TestHandleMessageGuards:
    def test_skips_message_from_disallowed_channel(self) -> None:
        client = MagicMock()
        dispatcher = MagicMock()
        config = _make_config(allowed_channel_ids=["C999"])
        pipeline = _make_pipeline(config)

        handle_message(
            _make_event(attachments=[{"text": _ALERTMANAGER_TEXT}]),
            client, config, pipeline, dispatcher,
        )

        dispatcher.dispatch.assert_not_called()
        client.chat_postMessage.assert_not_called()

    def test_processes_message_from_allowed_channel(self) -> None:
        client = MagicMock()
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = MagicMock(summary="ok")
        config = _make_config(allowed_channel_ids=["C123"])
        pipeline = _make_pipeline(config)

        handle_message(
            _make_event(attachments=[{"text": _ALERTMANAGER_TEXT}]),
            client, config, pipeline, dispatcher,
        )

        dispatcher.dispatch.assert_called_once()

    def test_skips_own_bot_message(self) -> None:
        """Messages from our own bot (replies we posted) must be skipped to prevent loops."""
        client = MagicMock()
        dispatcher = MagicMock()
        config = _make_config()
        pipeline = _make_pipeline(config)

        handle_message(
            _make_event(attachments=[{"text": _ALERTMANAGER_TEXT}], bot_id=OWN_BOT_ID),
            client, config, pipeline, dispatcher,
            own_bot_id=OWN_BOT_ID,
        )

        dispatcher.dispatch.assert_not_called()
        client.chat_postMessage.assert_not_called()

    def test_does_not_skip_alertmanager_webhook_bot(self) -> None:
        """Alertmanager sends via Incoming Webhook which also carries a bot_id.
        These must NOT be filtered — they are the alerts we want to process."""
        client = MagicMock()
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = MagicMock(summary="ok")
        config = _make_config()
        pipeline = _make_pipeline(config)

        handle_message(
            _make_event(
                attachments=[{"text": _ALERTMANAGER_TEXT}],
                bot_id=ALERTMANAGER_BOT_ID,
            ),
            client, config, pipeline, dispatcher,
            own_bot_id=OWN_BOT_ID,
        )

        dispatcher.dispatch.assert_called_once()

    def test_does_not_skip_cloudwatch_webhook_bot(self) -> None:
        """CloudWatch Lambda also posts via webhook — must not be filtered."""
        client = MagicMock()
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = MagicMock(summary="ok")
        config = _make_config()
        pipeline = _make_pipeline(config)

        handle_message(
            _make_event(
                attachments=[{"text": _CLOUDWATCH_TEXT}],
                bot_id=CLOUDWATCH_BOT_ID,
            ),
            client, config, pipeline, dispatcher,
            own_bot_id=OWN_BOT_ID,
        )

        dispatcher.dispatch.assert_called_once()


# ---------------------------------------------------------------------------
# handle_message — alert parsing
# ---------------------------------------------------------------------------


class TestHandleMessageParsing:
    def test_silently_skips_plain_message(self) -> None:
        client = MagicMock()
        dispatcher = MagicMock()
        config = _make_config()
        pipeline = _make_pipeline(config)

        handle_message(_make_event(text="hey team"), client, config, pipeline, dispatcher)

        dispatcher.dispatch.assert_not_called()
        client.chat_postMessage.assert_not_called()

    def test_parses_alertmanager_from_attachment(self) -> None:
        client = MagicMock()
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = MagicMock(summary="ok")
        config = _make_config()
        pipeline = _make_pipeline(config)

        handle_message(
            _make_event(attachments=[{"text": _ALERTMANAGER_TEXT}]),
            client, config, pipeline, dispatcher,
        )

        dispatcher.dispatch.assert_called_once()
        alert = dispatcher.dispatch.call_args.args[0]
        assert alert.alert_name == "HostOutOfMemory"
        assert alert.source == "alertmanager"

    def test_parses_cloudwatch_from_attachment(self) -> None:
        client = MagicMock()
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = MagicMock(summary="ok")
        config = _make_config()
        pipeline = _make_pipeline(config)

        handle_message(
            _make_event(attachments=[{"text": _CLOUDWATCH_TEXT}]),
            client, config, pipeline, dispatcher,
        )

        dispatcher.dispatch.assert_called_once()
        alert = dispatcher.dispatch.call_args.args[0]
        assert alert.alert_name == "HighCPUUtilization"
        assert alert.source == "cloudwatch_alarm"

    def test_parses_alert_from_event_text_when_no_attachments(self) -> None:
        client = MagicMock()
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = MagicMock(summary="ok")
        config = _make_config()
        pipeline = _make_pipeline(config)

        handle_message(
            _make_event(text=_CLOUDWATCH_TEXT),
            client, config, pipeline, dispatcher,
        )

        dispatcher.dispatch.assert_called_once()


# ---------------------------------------------------------------------------
# handle_message — control pipeline gating
# ---------------------------------------------------------------------------


class TestHandleMessageControlGating:
    def test_skips_when_alert_not_in_allowlist(self) -> None:
        client = MagicMock()
        dispatcher = MagicMock()
        config = _make_config(allowlist=["OtherAlert"])
        pipeline = _make_pipeline(config)

        handle_message(
            _make_event(attachments=[{"text": _ALERTMANAGER_TEXT}]),
            client, config, pipeline, dispatcher,
        )

        dispatcher.dispatch.assert_not_called()
        client.chat_postMessage.assert_not_called()

    def test_dispatches_when_allowlist_is_empty(self) -> None:
        client = MagicMock()
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = MagicMock(summary="ok")
        config = _make_config(allowlist=[])
        pipeline = _make_pipeline(config)

        handle_message(
            _make_event(attachments=[{"text": _ALERTMANAGER_TEXT}]),
            client, config, pipeline, dispatcher,
        )

        dispatcher.dispatch.assert_called_once()

    def test_skips_when_alert_in_denylist(self) -> None:
        client = MagicMock()
        dispatcher = MagicMock()
        config = _make_config(denylist=["HostOutOfMemory"])
        pipeline = _make_pipeline(config)

        handle_message(
            _make_event(attachments=[{"text": _ALERTMANAGER_TEXT}]),
            client, config, pipeline, dispatcher,
        )

        dispatcher.dispatch.assert_not_called()


# ---------------------------------------------------------------------------
# handle_message — record_investigation timing and Slack reply
# ---------------------------------------------------------------------------


class TestHandleMessageRecordAndReply:
    def test_reply_uses_formatted_investigation_message(self) -> None:
        client = MagicMock()
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = MagicMock(
            summary="deployment medication-service is healthy: 2/2 ready, 2 available",
            result_state="success",
            actions_attempted=["get_deployment_status"],
        )
        config = _make_config()
        pipeline = _make_pipeline(config)

        handle_message(
            _make_event(attachments=[{"text": _ALERTMANAGER_TEXT}], ts="111.000"),
            client, config, pipeline, dispatcher,
        )

        reply_text = client.chat_postMessage.call_args.kwargs["text"]
        assert "*Investigation Result*" in reply_text
        assert "*Alert:* HostOutOfMemory" in reply_text
        assert "*Target:* host/ip-172-16-52-233.ap-east-1.compute.internal" in reply_text
        assert "*Check:* get_deployment_status" in reply_text

    def test_record_called_after_successful_dispatch(self) -> None:
        """Dispatch success → record_investigation → second identical alert is in cooldown."""
        client = MagicMock()
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = MagicMock(summary="result")
        config = _make_config(cooldown_seconds=300.0)
        store = InMemoryAlertStateStore()
        policy = ControlPolicy(
            owned_environments=frozenset(config.owned_environments),
            cooldown_seconds=300.0,
            rate_limit_count=100,
            rate_limit_window_seconds=60.0,
        )
        pipeline = ControlPipeline(policy, store)

        handle_message(
            _make_event(attachments=[{"text": _ALERTMANAGER_TEXT}], ts="100.000"),
            client, config, pipeline, dispatcher,
        )
        handle_message(
            _make_event(attachments=[{"text": _ALERTMANAGER_TEXT}], ts="200.000"),
            client, config, pipeline, dispatcher,
        )

        assert dispatcher.dispatch.call_count == 1

    def test_record_not_called_when_dispatch_returns_none(self) -> None:
        """Dispatch returns None → no record → second identical alert is not in cooldown."""
        client = MagicMock()
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = None
        config = _make_config(cooldown_seconds=300.0)
        store = InMemoryAlertStateStore()
        policy = ControlPolicy(
            owned_environments=frozenset(config.owned_environments),
            cooldown_seconds=300.0,
            rate_limit_count=100,
            rate_limit_window_seconds=60.0,
        )
        pipeline = ControlPipeline(policy, store)

        handle_message(
            _make_event(attachments=[{"text": _ALERTMANAGER_TEXT}], ts="100.000"),
            client, config, pipeline, dispatcher,
        )
        handle_message(
            _make_event(attachments=[{"text": _ALERTMANAGER_TEXT}], ts="200.000"),
            client, config, pipeline, dispatcher,
        )

        assert dispatcher.dispatch.call_count == 2

    def test_no_slack_reply_when_dispatch_returns_none(self) -> None:
        client = MagicMock()
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = None
        config = _make_config()
        pipeline = _make_pipeline(config)

        handle_message(
            _make_event(attachments=[{"text": _ALERTMANAGER_TEXT}]),
            client, config, pipeline, dispatcher,
        )

        client.chat_postMessage.assert_not_called()

    def test_replies_to_thread_ts_when_in_thread(self) -> None:
        client = MagicMock()
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = MagicMock(summary="done")
        config = _make_config()
        pipeline = _make_pipeline(config)

        handle_message(
            _make_event(
                attachments=[{"text": _ALERTMANAGER_TEXT}],
                ts="111.000",
                thread_ts="100.000",
            ),
            client, config, pipeline, dispatcher,
        )

        client.chat_postMessage.assert_called_once_with(
            channel="C123",
            thread_ts="100.000",
            text=ANY,
        )

    def test_opens_new_thread_from_message_ts(self) -> None:
        client = MagicMock()
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = MagicMock(summary="done")
        config = _make_config()
        pipeline = _make_pipeline(config)

        handle_message(
            _make_event(attachments=[{"text": _ALERTMANAGER_TEXT}], ts="111.000"),
            client, config, pipeline, dispatcher,
        )

        client.chat_postMessage.assert_called_once_with(
            channel="C123",
            thread_ts="111.000",
            text=ANY,
        )
