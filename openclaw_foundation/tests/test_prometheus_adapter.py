import json

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
