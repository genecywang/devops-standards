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
