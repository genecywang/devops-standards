from types import SimpleNamespace
from unittest.mock import Mock, call

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
        metadata=SimpleNamespace(name="dev-api-123"),
        status=SimpleNamespace(
            phase="Running",
            container_statuses=[
                SimpleNamespace(
                    name="app",
                    ready=True,
                    image="example:v1",
                    restart_count=2,
                    state=SimpleNamespace(
                        waiting=None,
                        terminated=SimpleNamespace(reason="OOMKilled", exit_code=137),
                    ),
                )
            ],
        ),
        spec=SimpleNamespace(node_name="node-a"),
    )

    adapter = RealKubernetesProviderAdapter(api)

    result = adapter.get_pod_status(
        cluster="staging-main",
        namespace="dev",
        pod_name="dev-api-123",
    )

    assert result == {
        "pod_name": "dev-api-123",
        "namespace": "dev",
        "phase": "Running",
        "container_statuses": [
            {
                "name": "app",
                "ready": True,
                "image": "example:v1",
                "restart_count": 2,
                "state": {
                    "terminated_reason": "OOMKilled",
                    "terminated_exit_code": 137,
                },
            }
        ],
        "node_name": "node-a",
    }


def test_real_adapter_raises_domain_error_on_api_failure() -> None:
    api = Mock()
    api.read_namespaced_pod_status.side_effect = RuntimeError("boom")

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesApiError, match="failed to read pod status"):
        adapter.get_pod_status(
            cluster="staging-main",
            namespace="dev",
            pod_name="dev-api-123",
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
            namespace="dev",
            pod_name="dev-api-123",
        )


def test_real_adapter_maps_403_to_access_denied() -> None:
    api = Mock()
    api.read_namespaced_pod_status.side_effect = ApiException(status=403, reason="Forbidden")

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesAccessDeniedError, match="kubernetes access denied"):
        adapter.get_pod_status(
            cluster="staging-main",
            namespace="dev",
            pod_name="dev-api-123",
        )


def test_real_adapter_maps_404_to_resource_not_found() -> None:
    api = Mock()
    api.read_namespaced_pod_status.side_effect = ApiException(status=404, reason="Not Found")

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesResourceNotFoundError, match="pod not found"):
        adapter.get_pod_status(
            cluster="staging-main",
            namespace="dev",
            pod_name="dev-api-123",
        )


def test_real_adapter_handles_missing_optional_exception_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    api = Mock()
    api.read_namespaced_pod_status.side_effect = RuntimeError("boom")

    monkeypatch.setattr("openclaw_foundation.adapters.kubernetes.ApiException", None)
    monkeypatch.setattr("openclaw_foundation.adapters.kubernetes.NameResolutionError", None)
    monkeypatch.setattr("openclaw_foundation.adapters.kubernetes.ConnectTimeoutError", None)
    monkeypatch.setattr("openclaw_foundation.adapters.kubernetes.MaxRetryError", None)
    monkeypatch.setattr("openclaw_foundation.adapters.kubernetes._API_EXCEPTION_TYPES", ())
    monkeypatch.setattr(
        "openclaw_foundation.adapters.kubernetes._ENDPOINT_UNREACHABLE_EXCEPTION_TYPES",
        (),
    )

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesApiError, match="failed to read pod status"):
        adapter.get_pod_status(
            cluster="staging-main",
            namespace="dev",
            pod_name="dev-api-123",
        )


def test_real_adapter_finds_pod_by_ip_within_provided_namespaces_only() -> None:
    pod = SimpleNamespace(
        metadata=SimpleNamespace(name="dev-api-123", namespace="dev"),
        status=SimpleNamespace(pod_ip="10.0.1.23"),
    )
    api = Mock()
    api.list_namespaced_pod.side_effect = [
        SimpleNamespace(items=[]),
        SimpleNamespace(items=[pod]),
    ]

    adapter = RealKubernetesProviderAdapter(api)

    result = adapter.find_pod_by_ip(
        cluster="staging-main",
        namespaces=["staging", "dev"],
        pod_ip="10.0.1.23",
    )

    assert result == {
        "namespace": "dev",
        "pod_name": "dev-api-123",
        "pod_ip": "10.0.1.23",
    }
    assert api.list_namespaced_pod.call_args_list == [
        call(namespace="staging", field_selector="status.podIP=10.0.1.23"),
        call(namespace="dev", field_selector="status.podIP=10.0.1.23"),
    ]


def test_real_adapter_find_service_for_pod_returns_none_when_namespace_outside_scope() -> None:
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


def test_real_adapter_returns_none_when_pod_ip_matches_multiple_namespaces() -> None:
    pod_a = SimpleNamespace(
        metadata=SimpleNamespace(name="dev-api-123", namespace="dev"),
        status=SimpleNamespace(pod_ip="10.0.1.23"),
    )
    pod_b = SimpleNamespace(
        metadata=SimpleNamespace(name="staging-api-123", namespace="staging"),
        status=SimpleNamespace(pod_ip="10.0.1.23"),
    )
    api = Mock()
    api.list_namespaced_pod.side_effect = [
        SimpleNamespace(items=[pod_a]),
        SimpleNamespace(items=[pod_b]),
    ]

    adapter = RealKubernetesProviderAdapter(api)

    result = adapter.find_pod_by_ip(
        cluster="staging-main",
        namespaces=["dev", "staging"],
        pod_ip="10.0.1.23",
    )

    assert result is None


def test_fake_adapter_get_deployment_status_returns_bounded_payload() -> None:
    adapter = FakeKubernetesProviderAdapter()

    result = adapter.get_deployment_status(
        cluster="staging-main",
        namespace="dev",
        deployment_name="dev-api",
    )

    assert result["deployment_name"] == "dev-api"
    assert result["desired_replicas"] == 3
    assert isinstance(result["conditions"], list)
    assert set(result["conditions"][0].keys()) == {"type", "status", "reason", "message"}


def test_fake_adapter_get_deployment_status_contains_redactable_condition_message() -> None:
    adapter = FakeKubernetesProviderAdapter()

    result = adapter.get_deployment_status(
        cluster="staging-main",
        namespace="dev",
        deployment_name="dev-api",
    )

    all_messages = " ".join(str(c["message"]) for c in result["conditions"])
    assert "Bearer" in all_messages


def test_fake_adapter_get_job_status_returns_bounded_payload() -> None:
    adapter = FakeKubernetesProviderAdapter()

    result = adapter.get_job_status(
        cluster="staging-main",
        namespace="dev",
        job_name="nightly-backfill-12345",
    )

    assert result["job_name"] == "nightly-backfill-12345"
    assert result["namespace"] == "dev"
    assert result["active"] == 0
    assert result["succeeded"] == 1
    assert result["owner_kind"] == "CronJob"
    assert result["owner_name"] == "nightly-backfill"
    assert isinstance(result["conditions"], list)


def test_fake_adapter_get_job_status_contains_redactable_condition_message() -> None:
    adapter = FakeKubernetesProviderAdapter()

    result = adapter.get_job_status(
        cluster="staging-main",
        namespace="dev",
        job_name="nightly-backfill-12345",
    )

    all_messages = " ".join(str(c["message"]) for c in result["conditions"])
    assert "Bearer" in all_messages


def test_fake_adapter_get_cronjob_status_returns_latest_job_payload() -> None:
    adapter = FakeKubernetesProviderAdapter()

    result = adapter.get_cronjob_status(
        cluster="staging-main",
        namespace="dev",
        cronjob_name="nightly-backfill",
    )

    assert result["cronjob_name"] == "nightly-backfill"
    assert result["schedule"] == "*/30 * * * *"
    assert result["suspend"] is False
    assert result["last_schedule_time"] == "2026-04-18T02:30:00Z"
    assert result["latest_job_name"] == "nightly-backfill-12345"
    assert result["succeeded"] == 1
    assert isinstance(result["conditions"], list)


def test_fake_adapter_find_pod_by_ip_returns_bounded_lookup_payload() -> None:
    adapter = FakeKubernetesProviderAdapter()

    result = adapter.find_pod_by_ip(
        cluster="staging-main",
        namespaces=["dev"],
        pod_ip="10.0.1.23",
    )

    assert result == {
        "namespace": "dev",
        "pod_name": "dev-api-123",
        "pod_ip": "10.0.1.23",
    }


def test_fake_adapter_find_pod_by_ip_returns_none_outside_allowed_namespaces() -> None:
    adapter = FakeKubernetesProviderAdapter()

    result = adapter.find_pod_by_ip(
        cluster="staging-main",
        namespaces=["staging"],
        pod_ip="10.0.1.23",
    )

    assert result is None


def test_fake_adapter_find_service_for_pod_returns_bounded_lookup_payload() -> None:
    adapter = FakeKubernetesProviderAdapter()

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


def test_fake_adapter_find_service_for_pod_uses_staging_fixture() -> None:
    adapter = FakeKubernetesProviderAdapter()

    result = adapter.find_service_for_pod(
        cluster="staging-main",
        namespaces=["staging"],
        namespace="staging",
        pod_name="staging-api-123",
    )

    assert result == {
        "namespace": "staging",
        "service_name": "staging-api",
    }


def test_fake_adapter_find_service_for_pod_returns_none_for_ambiguous_fixture() -> None:
    adapter = FakeKubernetesProviderAdapter()

    result = adapter.find_service_for_pod(
        cluster="staging-main",
        namespaces=["staging"],
        namespace="staging",
        pod_name="staging-api-ambiguous",
    )

    assert result is None


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
        namespace="dev",
        pod_name="dev-api-123",
    )

    api.list_namespaced_event.assert_called_once_with(
        namespace="dev",
        field_selector="involvedObject.name=dev-api-123",
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
        namespace="dev",
        pod_name="dev-api-123",
    )

    assert result[0]["last_timestamp"] is None


def test_real_adapter_get_deployment_status_maps_minimal_fields() -> None:
    deployment = SimpleNamespace(
        metadata=SimpleNamespace(name="dev-api"),
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

    result = adapter.get_deployment_status("staging-main", "dev", "dev-api")

    assert result["deployment_name"] == "dev-api"
    assert result["desired_replicas"] == 3
    assert result["ready_replicas"] == 2
    assert result["conditions"][0]["type"] == "Available"


def test_real_adapter_get_job_status_maps_owner_reference() -> None:
    job = SimpleNamespace(
        metadata=SimpleNamespace(
            name="nightly-backfill-12345",
            owner_references=[
                SimpleNamespace(
                    kind="CronJob",
                    name="nightly-backfill",
                    controller=True,
                )
            ],
        ),
        status=SimpleNamespace(
            active=0,
            succeeded=1,
            failed=0,
            completion_time=None,
            conditions=[
                SimpleNamespace(
                    type="Complete",
                    status="True",
                    reason="Completed",
                    message="Job has completed successfully.",
                )
            ],
        ),
    )
    batch_api = SimpleNamespace(read_namespaced_job_status=lambda name, namespace: job)
    adapter = RealKubernetesProviderAdapter(core_v1_api=None, batch_v1_api=batch_api)

    result = adapter.get_job_status("staging-main", "dev", "nightly-backfill-12345")

    assert result["job_name"] == "nightly-backfill-12345"
    assert result["owner_kind"] == "CronJob"
    assert result["owner_name"] == "nightly-backfill"


def test_real_adapter_get_cronjob_status_maps_latest_owned_job() -> None:
    ts_old = datetime.datetime(2026, 4, 18, 1, 0, 0, tzinfo=datetime.timezone.utc)
    ts_new = datetime.datetime(2026, 4, 18, 2, 0, 0, tzinfo=datetime.timezone.utc)
    last_schedule = datetime.datetime(2026, 4, 18, 2, 30, 0, tzinfo=datetime.timezone.utc)
    older_job = SimpleNamespace(
        metadata=SimpleNamespace(
            name="nightly-backfill-12344",
            creation_timestamp=ts_old,
            owner_references=[SimpleNamespace(kind="CronJob", name="nightly-backfill", controller=True)],
        ),
        status=SimpleNamespace(start_time=ts_old, completion_time=ts_old),
    )
    latest_job = SimpleNamespace(
        metadata=SimpleNamespace(
            name="nightly-backfill-12345",
            creation_timestamp=ts_new,
            owner_references=[SimpleNamespace(kind="CronJob", name="nightly-backfill", controller=True)],
        ),
        status=SimpleNamespace(start_time=ts_new, completion_time=None),
    )
    unrelated_job = SimpleNamespace(
        metadata=SimpleNamespace(
            name="other-job-1",
            creation_timestamp=ts_new,
            owner_references=[SimpleNamespace(kind="CronJob", name="other-cronjob", controller=True)],
        ),
        status=SimpleNamespace(start_time=ts_new, completion_time=None),
    )
    batch_api = Mock()
    batch_api.read_namespaced_cron_job_status.return_value = SimpleNamespace(
        spec=SimpleNamespace(schedule="*/30 * * * *", suspend=False),
        status=SimpleNamespace(last_schedule_time=last_schedule),
    )
    batch_api.list_namespaced_job.return_value = SimpleNamespace(items=[older_job, latest_job, unrelated_job])
    batch_api.read_namespaced_job_status.return_value = SimpleNamespace(
        metadata=SimpleNamespace(name="nightly-backfill-12345", owner_references=[]),
        status=SimpleNamespace(
            active=1,
            succeeded=0,
            failed=0,
            completion_time=None,
            conditions=[],
        ),
    )
    adapter = RealKubernetesProviderAdapter(core_v1_api=None, batch_v1_api=batch_api)

    result = adapter.get_cronjob_status("staging-main", "dev", "nightly-backfill")

    batch_api.read_namespaced_cron_job_status.assert_called_once_with(name="nightly-backfill", namespace="dev")
    batch_api.list_namespaced_job.assert_called_once_with(namespace="dev")
    batch_api.read_namespaced_job_status.assert_called_once_with(name="nightly-backfill-12345", namespace="dev")
    assert result["cronjob_name"] == "nightly-backfill"
    assert result["schedule"] == "*/30 * * * *"
    assert result["suspend"] is False
    assert result["last_schedule_time"] == "2026-04-18T02:30:00+00:00"
    assert result["latest_job_name"] == "nightly-backfill-12345"
    assert result["active"] == 1


def test_real_adapter_get_cronjob_status_handles_no_owned_jobs() -> None:
    batch_api = Mock()
    batch_api.read_namespaced_cron_job_status.return_value = SimpleNamespace(
        spec=SimpleNamespace(schedule="*/30 * * * *", suspend=True),
        status=SimpleNamespace(last_schedule_time=None),
    )
    batch_api.list_namespaced_job.return_value = SimpleNamespace(items=[])
    adapter = RealKubernetesProviderAdapter(core_v1_api=None, batch_v1_api=batch_api)

    result = adapter.get_cronjob_status("staging-main", "dev", "nightly-backfill")

    assert result == {
        "cronjob_name": "nightly-backfill",
        "namespace": "dev",
        "schedule": "*/30 * * * *",
        "suspend": True,
        "last_schedule_time": None,
        "latest_job_name": None,
        "active": 0,
        "succeeded": 0,
        "failed": 0,
        "conditions": [],
    }


def test_real_adapter_get_pod_events_maps_403_to_access_denied() -> None:
    api = Mock()
    api.list_namespaced_event.side_effect = ApiException(status=403, reason="Forbidden")

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesAccessDeniedError, match="kubernetes access denied"):
        adapter.get_pod_events(
            cluster="staging-main",
            namespace="dev",
            pod_name="dev-api-123",
        )


def test_real_adapter_get_pod_events_maps_404_to_resource_not_found() -> None:
    api = Mock()
    api.list_namespaced_event.side_effect = ApiException(status=404, reason="Not Found")

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesResourceNotFoundError, match="namespace not found"):
        adapter.get_pod_events(
            cluster="staging-main",
            namespace="dev",
            pod_name="dev-api-123",
        )


def test_real_adapter_get_pod_events_maps_generic_api_error() -> None:
    api = Mock()
    api.list_namespaced_event.side_effect = RuntimeError("boom")

    adapter = RealKubernetesProviderAdapter(api)

    with pytest.raises(KubernetesApiError, match="failed to list pod events"):
        adapter.get_pod_events(
            cluster="staging-main",
            namespace="dev",
            pod_name="dev-api-123",
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
            namespace="dev",
            pod_name="dev-api-123",
        )


# --- get_pod_events: Fake adapter ---


def test_fake_adapter_get_pod_events_returns_bounded_event_list() -> None:
    from openclaw_foundation.adapters.kubernetes import FakeKubernetesProviderAdapter

    adapter = FakeKubernetesProviderAdapter()

    result = adapter.get_pod_events(
        cluster="staging-main",
        namespace="dev",
        pod_name="dev-api-123",
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
        namespace="dev",
        pod_name="dev-api-123",
    )

    all_messages = " ".join(str(e["message"]) for e in result)
    assert "Bearer" in all_messages
