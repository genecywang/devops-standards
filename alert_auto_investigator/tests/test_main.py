from unittest.mock import MagicMock, patch

from alert_auto_investigator import __main__
from alert_auto_investigator.investigation.dispatcher import DEFAULT_TOOL_ROUTING
from alert_auto_investigator.models.resource_type import InvestigationPolicy, SUPPORT_MATRIX


def _set_required_env(monkeypatch) -> None:
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")
    monkeypatch.setenv("REGION_CODE", "ap-east-1")
    monkeypatch.setenv("FALLBACK_ENVIRONMENT", "dev")
    monkeypatch.setenv("OWNED_ENVIRONMENTS", "dev")


def test_main_fetches_bot_identity_and_passes_it_to_handler(monkeypatch) -> None:
    _set_required_env(monkeypatch)

    fake_client = MagicMock()
    fake_client.auth_test.return_value = {
        "bot_id": "B_SELF",
        "user_id": "U_SELF",
    }

    fake_app = MagicMock()
    fake_app.client = fake_client
    registered_handlers: dict[str, object] = {}

    def register(event_name: str):
        def decorator(func):
            registered_handlers[event_name] = func
            return func

        return decorator

    fake_app.event.side_effect = register

    fake_socket_handler = MagicMock()

    with (
        patch.object(__main__, "_load_slack_bolt", return_value=(MagicMock(return_value=fake_app), MagicMock(return_value=fake_socket_handler))),
        patch.object(__main__, "handle_message") as handle_message_mock,
    ):
        __main__.main()
        assert "message" in registered_handlers
        registered_handlers["message"]({"channel": "C1", "ts": "1.0"}, fake_client)
        handle_message_mock.assert_called_once()
        assert handle_message_mock.call_args.kwargs["own_bot_id"] == "B_SELF"
        assert handle_message_mock.call_args.kwargs["own_bot_user_id"] == "U_SELF"

    fake_client.auth_test.assert_called_once_with()
    fake_socket_handler.start.assert_called_once_with()


def test_main_uses_socket_mode_app_token(monkeypatch) -> None:
    _set_required_env(monkeypatch)

    fake_client = MagicMock()
    fake_client.auth_test.return_value = {
        "bot_id": "B_SELF",
        "user_id": "U_SELF",
    }

    fake_app = MagicMock()
    fake_app.client = fake_client
    fake_app.event.side_effect = lambda _: (lambda func: func)

    fake_app_class = MagicMock(return_value=fake_app)
    socket_mode_handler_mock = MagicMock()

    with (
        patch.object(__main__, "_load_slack_bolt", return_value=(fake_app_class, socket_mode_handler_mock)),
        patch.object(__main__, "handle_message"),
    ):
        __main__.main()

    socket_mode_handler_mock.assert_called_once_with(fake_app, "xapp-test")


def test_main_passes_default_tool_routing_to_dispatcher(monkeypatch) -> None:
    _set_required_env(monkeypatch)

    fake_client = MagicMock()
    fake_client.auth_test.return_value = {
        "bot_id": "B_SELF",
        "user_id": "U_SELF",
    }

    fake_app = MagicMock()
    fake_app.client = fake_client
    fake_app.event.side_effect = lambda _: (lambda func: func)

    fake_socket_handler = MagicMock()

    with (
        patch.object(__main__, "_load_slack_bolt", return_value=(MagicMock(return_value=fake_app), MagicMock(return_value=fake_socket_handler))),
        patch.object(__main__, "build_runner", return_value=MagicMock()),
        patch.object(__main__, "OpenClawDispatcher") as dispatcher_cls,
        patch.object(__main__, "handle_message"),
    ):
        __main__.main()

    _, investigation_config = dispatcher_cls.call_args.args
    assert investigation_config.tool_routing == DEFAULT_TOOL_ROUTING


def test_all_investigate_resource_types_have_default_tool_routing() -> None:
    investigate_resource_types = {
        resource_type
        for resource_type, policy in SUPPORT_MATRIX.items()
        if policy is InvestigationPolicy.INVESTIGATE
    }

    assert investigate_resource_types <= set(DEFAULT_TOOL_ROUTING)
