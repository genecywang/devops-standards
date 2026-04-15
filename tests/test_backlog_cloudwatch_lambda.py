import importlib.util
from pathlib import Path


def load_lambda_module():
    module_path = Path(__file__).resolve().parents[1] / "backlog" / "aws" / "lambda.py"
    spec = importlib.util.spec_from_file_location("cloudwatch_lambda_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_alarm_message(**overrides):
    payload = {
        "AlarmName": "p-rds-shuriken_Blocked_Transactions",
        "AWSAccountId": "416885395773",
        "AlarmArn": "arn:aws:cloudwatch:ap-northeast-1:416885395773:alarm:p-rds-shuriken_Blocked_Transactions",
        "NewStateValue": "ALARM",
        "StateChangeTime": "2026-04-13T15:02:59.759+0000",
        "Trigger": {
            "Dimensions": [
                {"name": "DBInstanceIdentifier", "value": "shuriken"},
            ]
        },
    }
    payload.update(overrides)
    return payload


def test_build_cloudwatch_console_url_uses_alarm_region() -> None:
    module = load_lambda_module()

    url = module._build_cloudwatch_console_url(
        make_alarm_message(
            AlarmArn="arn:aws:cloudwatch:us-west-2:416885395773:alarm:test-alarm",
            AlarmName="test-alarm",
        )
    )

    assert "us-west-2.console.aws.amazon.com" in url
    assert "region=us-west-2" in url
    assert "alarm:test-alarm" in url


def test_get_alert_visuals_supports_insufficient_data() -> None:
    module = load_lambda_module()

    visuals = module._get_alert_visuals("INSUFFICIENT_DATA")

    assert visuals["text"] == "INSUFFICIENT_DATA"
    assert visuals["color"] == "#d9a404"
    assert visuals["emoji"]
