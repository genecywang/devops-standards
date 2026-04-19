from alert_auto_investigator.config import InvestigatorConfig


def test_from_env_parses_allowed_channel_ids(monkeypatch) -> None:
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")
    monkeypatch.setenv("REGION_CODE", "ap-east-1")
    monkeypatch.setenv("FALLBACK_ENVIRONMENT", "dev")
    monkeypatch.setenv("OWNED_ENVIRONMENTS", "dev")
    monkeypatch.setenv("ALERT_INVESTIGATOR_ALLOWED_CHANNEL_IDS", "C123, C456")

    config = InvestigatorConfig.from_env()

    assert config.allowed_channel_ids == ["C123", "C456"]


def test_from_env_defaults_assist_mode_to_off(monkeypatch) -> None:
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")
    monkeypatch.setenv("REGION_CODE", "ap-east-1")
    monkeypatch.setenv("FALLBACK_ENVIRONMENT", "dev")
    monkeypatch.setenv("OWNED_ENVIRONMENTS", "dev")

    config = InvestigatorConfig.from_env()

    assert config.assist_mode == "off"


def test_from_env_parses_shadow_assist_mode(monkeypatch) -> None:
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")
    monkeypatch.setenv("REGION_CODE", "ap-east-1")
    monkeypatch.setenv("FALLBACK_ENVIRONMENT", "dev")
    monkeypatch.setenv("OWNED_ENVIRONMENTS", "dev")
    monkeypatch.setenv("OPENCLAW_READONLY_ASSIST_MODE", "shadow")

    config = InvestigatorConfig.from_env()

    assert config.assist_mode == "shadow"
