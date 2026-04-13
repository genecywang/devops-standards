from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from kubernetes.client import ApiException
from urllib3.exceptions import NameResolutionError

from openclaw_foundation.adapters.kubernetes import (
    KubernetesAccessDeniedError,
    KubernetesApiError,
    KubernetesConfigError,
    KubernetesEndpointUnreachableError,
    KubernetesError,
    KubernetesResourceNotFoundError,
    RealKubernetesProviderAdapter,
    build_core_v1_api,
)


def test_kubernetes_domain_errors_share_common_base() -> None:
    assert issubclass(KubernetesConfigError, KubernetesError)
    assert issubclass(KubernetesEndpointUnreachableError, KubernetesError)
    assert issubclass(KubernetesAccessDeniedError, KubernetesError)
    assert issubclass(KubernetesResourceNotFoundError, KubernetesError)
    assert issubclass(KubernetesApiError, KubernetesError)


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


def test_real_adapter_maps_name_resolution_error_to_endpoint_unreachable() -> None:
    api = Mock()
    api.read_namespaced_pod_status.side_effect = NameResolutionError(
        "example.invalid",
        object(),
        OSError("dns failed"),
    )

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesEndpointUnreachableError, match="cluster endpoint unreachable"):
        adapter.get_pod_status(
            cluster="staging-main",
            namespace="payments",
            pod_name="payments-api-123",
        )


def test_real_adapter_maps_403_to_access_denied() -> None:
    api = Mock()
    api.read_namespaced_pod_status.side_effect = ApiException(status=403, reason="Forbidden")

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesAccessDeniedError, match="kubernetes access denied"):
        adapter.get_pod_status(
            cluster="staging-main",
            namespace="payments",
            pod_name="payments-api-123",
        )


def test_real_adapter_maps_404_to_resource_not_found() -> None:
    api = Mock()
    api.read_namespaced_pod_status.side_effect = ApiException(status=404, reason="Not Found")

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesResourceNotFoundError, match="pod not found"):
        adapter.get_pod_status(
            cluster="staging-main",
            namespace="payments",
            pod_name="payments-api-123",
        )
