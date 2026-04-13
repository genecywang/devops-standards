import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from openclaw_foundation.adapters.kubernetes import FakeKubernetesProviderAdapter, KubernetesConfigError
from openclaw_foundation.cli import build_provider_adapter, main, parse_args


def test_build_provider_adapter_is_importable() -> None:
    assert callable(build_provider_adapter)


def test_parse_args_defaults_provider_to_fake() -> None:
    args = parse_args(["--fixture", "openclaw_foundation/fixtures/investigation_request.json"])
    assert args.provider == "fake"


def test_build_provider_adapter_returns_fake_provider() -> None:
    adapter = build_provider_adapter("fake")
    assert isinstance(adapter, FakeKubernetesProviderAdapter)


def test_build_provider_adapter_returns_real_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_factory = Mock(return_value="core-v1")
    fake_adapter = Mock(return_value="real-adapter")

    monkeypatch.setattr("openclaw_foundation.cli.build_core_v1_api", fake_factory)
    monkeypatch.setattr("openclaw_foundation.cli.RealKubernetesProviderAdapter", fake_adapter)

    result = build_provider_adapter("real")

    assert result == "real-adapter"
    fake_factory.assert_called_once_with()
    fake_adapter.assert_called_once_with("core-v1")


def test_main_propagates_real_provider_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "openclaw_foundation.cli.build_provider_adapter",
        lambda provider: (_ for _ in ()).throw(KubernetesConfigError("unable to load kubernetes config")),
    )

    with pytest.raises(KubernetesConfigError, match="unable to load kubernetes config"):
        main(
            [
                "--fixture",
                "openclaw_foundation/fixtures/investigation_request.json",
                "--provider",
                "real",
            ]
        )


def test_cli_outputs_success_response() -> None:
    project_root = Path(__file__).resolve().parents[1]
    env = {
        "PYTHONPATH": str(project_root / "src"),
    }

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "openclaw_foundation.cli",
            "--fixture",
            str(project_root / "fixtures" / "investigation_request.json"),
        ],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )

    payload = json.loads(completed.stdout)

    assert payload["request_id"] == "req-001"
    assert payload["result_state"] == "success"
    assert "payments-api-123" in payload["summary"]
