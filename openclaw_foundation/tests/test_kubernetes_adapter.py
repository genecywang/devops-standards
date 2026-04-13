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
    FakeKubernetesProviderAdapter,
    KubernetesError,
    KubernetesResourceNotFoundError,
    RealKubernetesProviderAdapter,
    build_apps_v1_api,
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


def test_build_apps_v1_api_uses_incluster_first(monkeypatch: pytest.MonkeyPatch) -> None:
    load_incluster_config = Mock()
    load_kube_config = Mock()
    apps_v1_api = Mock(return_value="apps-v1")

    monkeypatch.setattr(
        "openclaw_foundation.adapters.kubernetes.kube_config",
        SimpleNamespace(
            load_incluster_config=load_incluster_config,
            load_kube_config=load_kube_config,
        ),
    )
    monkeypatch.setattr(
        "openclaw_foundation.adapters.kubernetes.client",
        SimpleNamespace(AppsV1Api=apps_v1_api),
    )

    result = build_apps_v1_api()

    assert result == "apps-v1"
    load_incluster_config.assert_called_once_with()
    load_kube_config.assert_not_called()


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


def test_fake_adapter_get_deployment_status_returns_bounded_payload() -> None:
    adapter = FakeKubernetesProviderAdapter()

    result = adapter.get_deployment_status(
        cluster="staging-main",
        namespace="payments",
        deployment_name="payments-api",
    )

    assert result["deployment_name"] == "payments-api"
    assert result["desired_replicas"] == 3
    assert isinstance(result["conditions"], list)
    assert set(result["conditions"][0].keys()) == {"type", "status", "reason", "message"}


def test_fake_adapter_get_deployment_status_contains_redactable_condition_message() -> None:
    adapter = FakeKubernetesProviderAdapter()

    result = adapter.get_deployment_status(
        cluster="staging-main",
        namespace="payments",
        deployment_name="payments-api",
    )

    all_messages = " ".join(str(c["message"]) for c in result["conditions"])
    assert "Bearer" in all_messages


# --- get_pod_events: Fake adapter ---


import datetime


# --- get_pod_events: Real adapter ---


def test_real_adapter_maps_pod_events_payload() -> None:
    api = Mock()
    ts = datetime.datetime(2026, 4, 13, 12, 0, 0, tzinfo=datetime.timezone.utc)
    api.list_namespaced_event.return_value = SimpleNamespace(
        items=[
            SimpleNamespace(
                type="Warning",
                reason="BackOff",
                message="Back-off restarting failed container",
                count=3,
                last_timestamp=ts,
            )
        ]
    )

    adapter = RealKubernetesProviderAdapter(api)
    result = adapter.get_pod_events(
        cluster="staging-main",
        namespace="payments",
        pod_name="payments-api-123",
    )

    api.list_namespaced_event.assert_called_once_with(
        namespace="payments",
        field_selector="involvedObject.name=payments-api-123",
    )
    assert result == [
        {
            "type": "Warning",
            "reason": "BackOff",
            "message": "Back-off restarting failed container",
            "count": 3,
            "last_timestamp": "2026-04-13T12:00:00+00:00",
        }
    ]


def test_real_adapter_get_pod_events_maps_none_timestamp() -> None:
    api = Mock()
    api.list_namespaced_event.return_value = SimpleNamespace(
        items=[
            SimpleNamespace(
                type="Normal",
                reason="Pulled",
                message="image pulled",
                count=1,
                last_timestamp=None,
            )
        ]
    )

    adapter = RealKubernetesProviderAdapter(api)
    result = adapter.get_pod_events(
        cluster="staging-main",
        namespace="payments",
        pod_name="payments-api-123",
    )

    assert result[0]["last_timestamp"] is None


def test_real_adapter_get_deployment_status_maps_minimal_fields() -> None:
    deployment = SimpleNamespace(
        metadata=SimpleNamespace(name="payments-api"),
        status=SimpleNamespace(
            ready_replicas=2,
            available_replicas=2,
            updated_replicas=3,
            conditions=[
                SimpleNamespace(
                    type="Available",
                    status="True",
                    reason="MinimumReplicasAvailable",
                    message="Deployment has minimum availability.",
                )
            ],
        ),
        spec=SimpleNamespace(replicas=3),
    )
    apps_api = SimpleNamespace(read_namespaced_deployment_status=lambda name, namespace: deployment)
    adapter = RealKubernetesProviderAdapter(core_v1_api=None, apps_v1_api=apps_api)

    result = adapter.get_deployment_status("staging-main", "payments", "payments-api")

    assert result["deployment_name"] == "payments-api"
    assert result["desired_replicas"] == 3
    assert result["ready_replicas"] == 2
    assert result["conditions"][0]["type"] == "Available"


def test_real_adapter_get_pod_events_maps_403_to_access_denied() -> None:
    api = Mock()
    api.list_namespaced_event.side_effect = ApiException(status=403, reason="Forbidden")

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesAccessDeniedError, match="kubernetes access denied"):
        adapter.get_pod_events(
            cluster="staging-main",
            namespace="payments",
            pod_name="payments-api-123",
        )


def test_real_adapter_get_pod_events_maps_404_to_resource_not_found() -> None:
    api = Mock()
    api.list_namespaced_event.side_effect = ApiException(status=404, reason="Not Found")

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesResourceNotFoundError, match="namespace not found"):
        adapter.get_pod_events(
            cluster="staging-main",
            namespace="payments",
            pod_name="payments-api-123",
        )


def test_real_adapter_get_pod_events_maps_generic_api_error() -> None:
    api = Mock()
    api.list_namespaced_event.side_effect = RuntimeError("boom")

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesApiError, match="failed to list pod events"):
        adapter.get_pod_events(
            cluster="staging-main",
            namespace="payments",
            pod_name="payments-api-123",
        )


def test_real_adapter_get_pod_events_maps_name_resolution_error() -> None:
    api = Mock()
    api.list_namespaced_event.side_effect = NameResolutionError(
        "example.invalid",
        object(),
        OSError("dns failed"),
    )

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesEndpointUnreachableError, match="cluster endpoint unreachable"):
        adapter.get_pod_events(
            cluster="staging-main",
            namespace="payments",
            pod_name="payments-api-123",
        )


# --- get_pod_events: Fake adapter ---


def test_fake_adapter_get_pod_events_returns_bounded_event_list() -> None:
    from openclaw_foundation.adapters.kubernetes import FakeKubernetesProviderAdapter

    adapter = FakeKubernetesProviderAdapter()

    result = adapter.get_pod_events(
        cluster="staging-main",
        namespace="payments",
        pod_name="payments-api-123",
    )

    assert isinstance(result, list)
    assert len(result) >= 1
    first = result[0]
    assert set(first.keys()) == {"type", "reason", "message", "count", "last_timestamp"}


def test_fake_adapter_get_pod_events_message_contains_redactable_content() -> None:
    from openclaw_foundation.adapters.kubernetes import FakeKubernetesProviderAdapter

    adapter = FakeKubernetesProviderAdapter()

    result = adapter.get_pod_events(
        cluster="staging-main",
        namespace="payments",
        pod_name="payments-api-123",
    )

    all_messages = " ".join(str(e["message"]) for e in result)
    assert "Bearer" in all_messages
