from __future__ import annotations

from openclaw_foundation.adapters.kubernetes import (
    FakeKubernetesProviderAdapter,
    RealKubernetesProviderAdapter,
    build_apps_v1_api,
    build_batch_v1_api,
    build_core_v1_api,
)
from openclaw_foundation.adapters.aws import FakeAwsProviderAdapter, RealAwsProviderAdapter
from openclaw_foundation.adapters.prometheus import (
    FakePrometheusProviderAdapter,
    RealPrometheusProviderAdapter,
)
from openclaw_foundation.runtime.runner import OpenClawRunner
from openclaw_foundation.tools.aws_rds_instance_status import AwsRdsInstanceStatusTool
from openclaw_foundation.tools.kubernetes_cronjob_status import KubernetesCronJobStatusTool
from openclaw_foundation.tools.kubernetes_deployment_status import KubernetesDeploymentStatusTool
from openclaw_foundation.tools.kubernetes_job_status import KubernetesJobStatusTool
from openclaw_foundation.tools.kubernetes_pod_events import KubernetesPodEventsTool
from openclaw_foundation.tools.kubernetes_pod_status import KubernetesPodStatusTool
from openclaw_foundation.tools.registry import ToolRegistry

from alert_auto_investigator.config import InvestigatorConfig
from alert_auto_investigator.service.stub_runner import StubInvestigationRunner


def build_runner(config: InvestigatorConfig) -> object:
    if config.provider == "stub":
        return StubInvestigationRunner()
    if config.provider == "real":
        return OpenClawRunner(build_registry(config))
    raise ValueError(f"Unsupported INVESTIGATION_PROVIDER: {config.provider!r}")


def build_registry(config: InvestigatorConfig) -> ToolRegistry:
    if config.provider == "real":
        if not config.prometheus_base_url:
            raise ValueError("OPENCLAW_PROMETHEUS_BASE_URL is required for real provider")
        kubernetes_adapter = RealKubernetesProviderAdapter(
            build_core_v1_api(),
            build_apps_v1_api(),
            build_batch_v1_api(),
        )
        prometheus_adapter = RealPrometheusProviderAdapter(
            base_url=config.prometheus_base_url,
        )
        aws_adapter = RealAwsProviderAdapter()
    else:
        kubernetes_adapter = FakeKubernetesProviderAdapter()
        prometheus_adapter = FakePrometheusProviderAdapter()
        aws_adapter = FakeAwsProviderAdapter()

    allowed_clusters = set(config.allowed_clusters or [])
    allowed_namespaces = set(config.allowed_namespaces or [])

    registry = ToolRegistry()
    registry.register(
        KubernetesPodStatusTool(
            adapter=kubernetes_adapter,
            allowed_clusters=allowed_clusters,
            allowed_namespaces=allowed_namespaces,
        )
    )
    registry.register(
        KubernetesPodEventsTool(
            adapter=kubernetes_adapter,
            allowed_clusters=allowed_clusters,
            allowed_namespaces=allowed_namespaces,
        )
    )
    registry.register(
        KubernetesDeploymentStatusTool(
            adapter=kubernetes_adapter,
            allowed_clusters=allowed_clusters,
            allowed_namespaces=allowed_namespaces,
        )
    )
    registry.register(
        KubernetesJobStatusTool(
            adapter=kubernetes_adapter,
            allowed_clusters=allowed_clusters,
            allowed_namespaces=allowed_namespaces,
        )
    )
    registry.register(
        KubernetesCronJobStatusTool(
            adapter=kubernetes_adapter,
            allowed_clusters=allowed_clusters,
            allowed_namespaces=allowed_namespaces,
        )
    )
    registry.register(AwsRdsInstanceStatusTool(adapter=aws_adapter))
    return registry
