from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from openclaw_foundation.adapters.kubernetes import KubernetesApiError
from openclaw_foundation.adapters.kubernetes import FakeKubernetesProviderAdapter
from openclaw_foundation.adapters.kubernetes import RealKubernetesProviderAdapter


def test_real_adapter_finds_service_for_pod_via_endpointslice() -> None:
    endpoint_slice = SimpleNamespace(
        metadata=SimpleNamespace(labels={"kubernetes.io/service-name": "dev-api"}),
        endpoints=[
            SimpleNamespace(
                target_ref=SimpleNamespace(kind="Pod", name="dev-api-123"),
            )
        ],
    )
    api = Mock()
    api.list_namespaced_endpoint_slice.return_value = SimpleNamespace(items=[endpoint_slice])

    adapter = RealKubernetesProviderAdapter(core_v1_api=Mock(), discovery_v1_api=api)

    result = adapter.find_service_for_pod(
        cluster="staging-main",
        namespaces=["dev"],
        namespace="dev",
        pod_name="dev-api-123",
    )

    assert result == {
        "namespace": "dev",
        "service_name": "dev-api",
    }
    api.list_namespaced_endpoint_slice.assert_called_once_with(namespace="dev")


def test_real_adapter_returns_none_when_service_match_is_ambiguous() -> None:
    endpoint_slice_a = SimpleNamespace(
        metadata=SimpleNamespace(labels={"kubernetes.io/service-name": "dev-api"}),
        endpoints=[
            SimpleNamespace(
                target_ref=SimpleNamespace(kind="Pod", name="dev-api-123"),
            )
        ],
    )
    endpoint_slice_b = SimpleNamespace(
        metadata=SimpleNamespace(labels={"kubernetes.io/service-name": "dev-api-canary"}),
        endpoints=[
            SimpleNamespace(
                target_ref=SimpleNamespace(kind="Pod", name="dev-api-123"),
            )
        ],
    )
    api = Mock()
    api.list_namespaced_endpoint_slice.return_value = SimpleNamespace(
        items=[endpoint_slice_a, endpoint_slice_b]
    )

    adapter = RealKubernetesProviderAdapter(core_v1_api=Mock(), discovery_v1_api=api)

    result = adapter.find_service_for_pod(
        cluster="staging-main",
        namespaces=["dev"],
        namespace="dev",
        pod_name="dev-api-123",
    )

    assert result is None
    api.list_namespaced_endpoint_slice.assert_called_once_with(namespace="dev")


def test_real_adapter_returns_none_when_namespace_is_outside_scope() -> None:
    api = Mock()

    adapter = RealKubernetesProviderAdapter(core_v1_api=Mock(), discovery_v1_api=api)

    result = adapter.find_service_for_pod(
        cluster="staging-main",
        namespaces=["staging"],
        namespace="dev",
        pod_name="dev-api-123",
    )

    assert result is None
    api.list_namespaced_endpoint_slice.assert_not_called()


def test_real_adapter_raises_api_error_when_discovery_client_missing() -> None:
    adapter = RealKubernetesProviderAdapter(core_v1_api=Mock(), discovery_v1_api=None)

    with pytest.raises(KubernetesApiError, match="failed to find service for pod"):
        adapter.find_service_for_pod(
            cluster="staging-main",
            namespaces=["dev"],
            namespace="dev",
            pod_name="dev-api-123",
        )


def test_fake_adapter_find_service_for_pod_returns_none_for_missing_fixture() -> None:
    adapter = FakeKubernetesProviderAdapter()

    result = adapter.find_service_for_pod(
        cluster="staging-main",
        namespaces=["dev"],
        namespace="dev",
        pod_name="dev-api-missing",
    )

    assert result is None
