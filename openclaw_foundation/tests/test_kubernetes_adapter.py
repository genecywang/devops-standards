from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from openclaw_foundation.adapters.kubernetes import (
    KubernetesApiError,
    KubernetesConfigError,
    RealKubernetesProviderAdapter,
    build_core_v1_api,
)


def test_build_core_v1_api_uses_incluster_first(monkeypatch: pytest.MonkeyPatch) -> None:
    load_incluster_config = Mock()
    load_kube_config = Mock()
    core_v1_api = Mock(return_value="core-v1")

    monkeypatch.setattr(
        "openclaw_foundation.adapters.kubernetes.kube_config",
        SimpleNamespace(
            load_incluster_config=load_incluster_config,
            load_kube_config=load_kube_config,
        ),
    )
    monkeypatch.setattr(
        "openclaw_foundation.adapters.kubernetes.client",
        SimpleNamespace(CoreV1Api=core_v1_api),
    )

    result = build_core_v1_api()

    assert result == "core-v1"
    load_incluster_config.assert_called_once_with()
    load_kube_config.assert_not_called()


def test_build_core_v1_api_falls_back_to_kubeconfig(monkeypatch: pytest.MonkeyPatch) -> None:
    load_incluster_config = Mock(side_effect=RuntimeError("no serviceaccount"))
    load_kube_config = Mock()
    core_v1_api = Mock(return_value="core-v1")

    monkeypatch.setattr(
        "openclaw_foundation.adapters.kubernetes.kube_config",
        SimpleNamespace(
            load_incluster_config=load_incluster_config,
            load_kube_config=load_kube_config,
        ),
    )
    monkeypatch.setattr(
        "openclaw_foundation.adapters.kubernetes.client",
        SimpleNamespace(CoreV1Api=core_v1_api),
    )

    result = build_core_v1_api()

    assert result == "core-v1"
    load_incluster_config.assert_called_once_with()
    load_kube_config.assert_called_once_with()


def test_build_core_v1_api_raises_config_error_when_no_loader_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "openclaw_foundation.adapters.kubernetes.client",
        SimpleNamespace(CoreV1Api=Mock(return_value="core-v1")),
    )
    monkeypatch.setattr(
        "openclaw_foundation.adapters.kubernetes.kube_config",
        SimpleNamespace(
            load_incluster_config=Mock(side_effect=RuntimeError("no serviceaccount")),
            load_kube_config=Mock(side_effect=RuntimeError("no kubeconfig")),
        ),
    )

    with pytest.raises(KubernetesConfigError, match="unable to load kubernetes config"):
        build_core_v1_api()


def test_real_adapter_maps_pod_status_payload() -> None:
    api = Mock()
    api.read_namespaced_pod_status.return_value = SimpleNamespace(
        metadata=SimpleNamespace(name="payments-api-123"),
        status=SimpleNamespace(
            phase="Running",
            container_statuses=[
                SimpleNamespace(
                    name="app",
                    ready=True,
                    image="example:v1",
                )
            ],
        ),
        spec=SimpleNamespace(node_name="node-a"),
    )

    adapter = RealKubernetesProviderAdapter(api)

    result = adapter.get_pod_status(
        cluster="staging-main",
        namespace="payments",
        pod_name="payments-api-123",
    )

    assert result == {
        "pod_name": "payments-api-123",
        "namespace": "payments",
        "phase": "Running",
        "container_statuses": [{"name": "app", "ready": True, "image": "example:v1"}],
        "node_name": "node-a",
    }


def test_real_adapter_raises_domain_error_on_api_failure() -> None:
    api = Mock()
    api.read_namespaced_pod_status.side_effect = RuntimeError("boom")

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesApiError, match="failed to read pod status"):
        adapter.get_pod_status(
            cluster="staging-main",
            namespace="payments",
            pod_name="payments-api-123",
        )
