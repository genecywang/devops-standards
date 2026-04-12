import json
import subprocess
import sys
from pathlib import Path


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
