import argparse
import json
from dataclasses import asdict
from pathlib import Path

from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.runtime.runner import OpenClawRunner
from openclaw_foundation.tools.fake_investigation import FakeInvestigationTool
from openclaw_foundation.tools.registry import ToolRegistry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    args = parser.parse_args()

    fixture_path = Path(args.fixture)
    payload = json.loads(fixture_path.read_text())
    request = InvestigationRequest.from_dict(payload)

    registry = ToolRegistry()
    registry.register(FakeInvestigationTool())
    response = OpenClawRunner(registry).run(request)
    print(json.dumps(asdict(response), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
