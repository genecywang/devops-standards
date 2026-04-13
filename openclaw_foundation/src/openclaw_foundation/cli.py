import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from openclaw_foundation.adapters.kubernetes import (
    FakeKubernetesProviderAdapter,
    KubernetesAccessDeniedError,
    KubernetesConfigError,
    KubernetesEndpointUnreachableError,
    KubernetesError,
    KubernetesResourceNotFoundError,
    RealKubernetesProviderAdapter,
    build_apps_v1_api,
    build_core_v1_api,
)
from openclaw_foundation.models.requests import InvestigationRequest
from openclaw_foundation.runtime.runner import OpenClawRunner
from openclaw_foundation.tools.fake_investigation import FakeInvestigationTool
from openclaw_foundation.tools.kubernetes_deployment_status import KubernetesDeploymentStatusTool
from openclaw_foundation.tools.kubernetes_pod_events import KubernetesPodEventsTool
from openclaw_foundation.tools.kubernetes_pod_status import KubernetesPodStatusTool
from openclaw_foundation.tools.registry import ToolRegistry


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--provider", choices=("fake", "real"), default="fake")
    return parser.parse_args(argv)


def build_provider_adapter(provider: str):
    if provider == "fake":
        return FakeKubernetesProviderAdapter()
    if provider == "real":
        return RealKubernetesProviderAdapter(build_core_v1_api(), build_apps_v1_api())
    raise ValueError(f"unsupported provider mode: {provider}")


def render_kubernetes_error(error: KubernetesError) -> str:
    if isinstance(error, KubernetesConfigError):
        next_check = "verify in-cluster identity or kubeconfig context"
    elif isinstance(error, KubernetesEndpointUnreachableError):
        next_check = "verify DNS, network path, VPN, or cluster endpoint"
    elif isinstance(error, KubernetesAccessDeniedError):
        next_check = "verify service account, IAM / RBAC permissions"
    elif isinstance(error, KubernetesResourceNotFoundError):
        next_check = "verify cluster, namespace, and pod_name"
    else:
        next_check = "inspect kubernetes client error details"
    return f"{error}\nnext check: {next_check}"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    fixture_path = Path(args.fixture)
    payload = json.loads(fixture_path.read_text())
    request = InvestigationRequest.from_dict(payload)

    try:
        provider_adapter = build_provider_adapter(args.provider)
        registry = ToolRegistry()
        registry.register(FakeInvestigationTool())
        registry.register(
            KubernetesPodStatusTool(
                adapter=provider_adapter,
                allowed_clusters={"staging-main"},
                allowed_namespaces={"payments"},
            )
        )
        registry.register(
            KubernetesPodEventsTool(
                adapter=provider_adapter,
                allowed_clusters={"staging-main"},
                allowed_namespaces={"payments"},
            )
        )
        registry.register(
            KubernetesDeploymentStatusTool(
                adapter=provider_adapter,
                allowed_clusters={"staging-main"},
                allowed_namespaces={"payments"},
            )
        )
        response = OpenClawRunner(registry).run(request)
        print(json.dumps(asdict(response), indent=2))
        return 0
    except KubernetesError as error:
        print(render_kubernetes_error(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
