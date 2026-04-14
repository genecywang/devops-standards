import json
from urllib.error import HTTPError

import pytest

from openclaw_foundation.adapters.prometheus import (
    FakePrometheusProviderAdapter,
    PrometheusQueryError,
    RealPrometheusProviderAdapter,
)


def test_fake_prometheus_adapter_returns_runtime_payload() -> None:
    adapter = FakePrometheusProviderAdapter()

    result = adapter.get_pod_runtime(
        namespace="dev",
        pod_name="dev-py3-h2s-apisvc-5596c5b6bb-7hrg7",
    )

    assert result["pod_name"] == "dev-py3-h2s-apisvc-5596c5b6bb-7hrg7"
    assert result["ready"] is True
    assert result["restart_count"] == 0
    assert result["recent_restart_increase"] == 0.0
    assert result["window"] == "15m"


def test_fake_prometheus_adapter_returns_cpu_usage_payload() -> None:
    adapter = FakePrometheusProviderAdapter()

    result = adapter.get_pod_cpu_usage(
        namespace="dev",
        pod_name="dev-py3-h2s-apisvc-5596c5b6bb-7hrg7",
    )

    assert result == {
        "namespace": "dev",
        "pod_name": "dev-py3-h2s-apisvc-5596c5b6bb-7hrg7",
        "avg_cpu_cores_5m": 0.03,
        "window": "5m",
    }


def test_fake_prometheus_adapter_returns_deployment_restart_rate_shape() -> None:
    adapter = FakePrometheusProviderAdapter()

    payload = adapter.get_deployment_restart_rate("payments", "payments-api")

    assert payload["namespace"] == "payments"
    assert payload["deployment_name"] == "payments-api"
    assert payload["recent_restarts_15m"] == 3
    assert payload["total_restarts"] == 7
    assert payload["pods_shown"] == 2
    assert payload["pods_total"] == 2
    assert payload["no_pods"] is False
    assert payload["window"] == "15m"
    assert len(payload["pod_breakdown"]) == 2


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_real_prometheus_adapter_aggregates_pod_runtime_queries(monkeypatch) -> None:
    payloads = iter(
        [
            {
                "status": "success",
                "data": {"result": [{"value": [1776068042.855, "1"]}]},
            },
            {
                "status": "success",
                "data": {
                    "result": [
                        {"value": [1776068042.912, "1"]},
                        {"value": [1776068042.912, "2"]},
                    ]
                },
            },
            {
                "status": "success",
                "data": {"result": [{"value": [1776068042.912, "3"]}]},
            },
        ]
    )

    monkeypatch.setattr(
        "openclaw_foundation.adapters.prometheus.urlopen",
        lambda url, timeout: _FakeHttpResponse(next(payloads)),
    )

    adapter = RealPrometheusProviderAdapter("https://prom.example.internal")
    result = adapter.get_pod_runtime("dev", "pod-123")

    assert result == {
        "namespace": "dev",
        "pod_name": "pod-123",
        "ready": True,
        "restart_count": 3,
        "recent_restart_increase": 3.0,
        "window": "15m",
    }


def test_real_prometheus_adapter_raises_query_error_on_non_success_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        "openclaw_foundation.adapters.prometheus.urlopen",
        lambda url, timeout: _FakeHttpResponse({"status": "error", "data": {}}),
    )

    adapter = RealPrometheusProviderAdapter("https://prom.example.internal")

    try:
        adapter.query_instant("up")
    except PrometheusQueryError as error:
        assert "non-success" in str(error)
    else:
        raise AssertionError("expected PrometheusQueryError")


def test_real_prometheus_adapter_raises_query_error_when_no_pod_metrics_exist(
    monkeypatch,
) -> None:
    payloads = iter(
        [
            {"status": "success", "data": {"result": []}},
            {"status": "success", "data": {"result": []}},
            {"status": "success", "data": {"result": []}},
        ]
    )

    monkeypatch.setattr(
        "openclaw_foundation.adapters.prometheus.urlopen",
        lambda url, timeout: _FakeHttpResponse(next(payloads)),
    )

    adapter = RealPrometheusProviderAdapter("https://prom.example.internal")

    try:
        adapter.get_pod_runtime("dev", "missing-pod")
    except PrometheusQueryError as error:
        assert "no metrics found for pod" in str(error)
    else:
        raise AssertionError("expected PrometheusQueryError")


def test_real_prometheus_adapter_logs_query_metadata_on_http_error(
    monkeypatch,
    caplog,
) -> None:
    def raising_urlopen(url, timeout):
        raise HTTPError(url, 400, "Bad Request", hdrs=None, fp=None)

    monkeypatch.setattr(
        "openclaw_foundation.adapters.prometheus.urlopen",
        raising_urlopen,
    )

    adapter = RealPrometheusProviderAdapter("https://prom.example.internal")

    with pytest.raises(PrometheusQueryError, match="failed to query prometheus"):
        adapter.query_instant("up", query_name="deployment_replicaset_lookup")

    assert "deployment_replicaset_lookup" in caplog.text
    assert "http_status=400" in caplog.text


def test_real_prometheus_adapter_builds_promql_safe_regex_union() -> None:
    adapter = RealPrometheusProviderAdapter("https://prom.example.internal")

    regex = adapter._regex_union(
        [
            "dev-py3-h2s-apisvc-5596c5b6bb",
            "payments.api-v2",
        ]
    )

    assert regex == "dev-py3-h2s-apisvc-5596c5b6bb|payments\\\\.api-v2"
    assert "\\-" not in regex


def test_real_prometheus_adapter_returns_pod_cpu_usage_payload(monkeypatch) -> None:
    adapter = RealPrometheusProviderAdapter(base_url="https://example.com")
    responses = [
        {
            "result": [
                {"metric": {"pod": "payments-api-pod-a"}, "value": [0, "0.125"]},
            ]
        },
    ]

    monkeypatch.setattr(adapter, "query_instant", lambda query, query_name="instant_query": responses.pop(0))

    payload = adapter.get_pod_cpu_usage("payments", "payments-api-pod-a")

    assert payload == {
        "namespace": "payments",
        "pod_name": "payments-api-pod-a",
        "avg_cpu_cores_5m": 0.125,
        "window": "5m",
    }


def test_real_prometheus_adapter_raises_when_no_cpu_metrics_exist(monkeypatch) -> None:
    adapter = RealPrometheusProviderAdapter(base_url="https://example.com")
    monkeypatch.setattr(
        adapter,
        "query_instant",
        lambda query, query_name="instant_query": {"result": []},
    )

    with pytest.raises(PrometheusQueryError, match="no cpu metrics found for pod"):
        adapter.get_pod_cpu_usage("payments", "missing-pod")


def test_real_prometheus_adapter_builds_deployment_restart_payload(monkeypatch) -> None:
    adapter = RealPrometheusProviderAdapter(base_url="https://example.com")
    responses = [
        {
            "result": [
                {"metric": {"replicaset": "payments-api-rs1"}, "value": [0, "1"]},
                {"metric": {"replicaset": "payments-api-rs2"}, "value": [0, "1"]},
            ]
        },
        {
            "result": [
                {"metric": {"pod": "payments-api-pod-a"}, "value": [0, "1"]},
                {"metric": {"pod": "payments-api-pod-b"}, "value": [0, "1"]},
            ]
        },
        {
            "result": [
                {"metric": {"pod": "payments-api-pod-a"}, "value": [0, "4"]},
                {"metric": {"pod": "payments-api-pod-b"}, "value": [0, "3"]},
            ]
        },
        {
            "result": [
                {"metric": {"pod": "payments-api-pod-a"}, "value": [0, "2"]},
                {"metric": {"pod": "payments-api-pod-b"}, "value": [0, "1"]},
            ]
        },
    ]

    monkeypatch.setattr(
        adapter,
        "query_instant",
        lambda query, query_name="instant_query": responses.pop(0),
    )

    payload = adapter.get_deployment_restart_rate("payments", "payments-api")

    assert payload["recent_restarts_15m"] == 3
    assert payload["total_restarts"] == 7
    assert payload["pods_shown"] == 2
    assert payload["pods_total"] == 2
    assert payload["no_pods"] is False
    assert payload["pod_breakdown"][0]["pod_name"] == "payments-api-pod-a"


def test_real_prometheus_adapter_raises_when_no_replicasets(monkeypatch) -> None:
    adapter = RealPrometheusProviderAdapter(base_url="https://example.com")
    monkeypatch.setattr(
        adapter,
        "query_instant",
        lambda query, query_name="instant_query": {"result": []},
    )

    try:
        adapter.get_deployment_restart_rate("payments", "payments-api")
        raise AssertionError("expected PrometheusQueryError")
    except PrometheusQueryError as error:
        assert str(error) == "no replicasets found for deployment"


def test_real_prometheus_adapter_returns_no_pods_when_q2_is_empty(monkeypatch) -> None:
    adapter = RealPrometheusProviderAdapter(base_url="https://example.com")
    responses = [
        {"result": [{"metric": {"replicaset": "payments-api-rs1"}, "value": [0, "1"]}]},
        {"result": []},
    ]

    monkeypatch.setattr(
        adapter,
        "query_instant",
        lambda query, query_name="instant_query": responses.pop(0),
    )

    payload = adapter.get_deployment_restart_rate("payments", "payments-api")

    assert payload["recent_restarts_15m"] == 0
    assert payload["total_restarts"] == 0
    assert payload["pod_breakdown"] == []
    assert payload["no_pods"] is True


def test_real_prometheus_adapter_returns_missing_metrics_shape_when_q3_q4_are_empty(
    monkeypatch,
) -> None:
    adapter = RealPrometheusProviderAdapter(base_url="https://example.com")
    responses = [
        {"result": [{"metric": {"replicaset": "payments-api-rs1"}, "value": [0, "1"]}]},
        {"result": [{"metric": {"pod": "payments-api-pod-a"}, "value": [0, "1"]}]},
        {"result": []},
        {"result": []},
    ]

    monkeypatch.setattr(
        adapter,
        "query_instant",
        lambda query, query_name="instant_query": responses.pop(0),
    )

    payload = adapter.get_deployment_restart_rate("payments", "payments-api")

    assert payload["recent_restarts_15m"] == 0
    assert payload["total_restarts"] == 0
    assert payload["pod_breakdown"] == []
    assert payload["no_pods"] is False
