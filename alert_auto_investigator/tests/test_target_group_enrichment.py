import pytest

from alert_auto_investigator.investigation.target_group_enrichment import (
    evaluate_target_group_enrichment,
)


def test_multi_ip_same_service_returns_high_confidence() -> None:
    result = evaluate_target_group_enrichment(
        target_type="ip",
        target_ips=["10.0.1.12", "10.0.1.13"],
        matched_pods=[
            {
                "namespace": "dev",
                "pod_name": "h2-api-abc",
                "pod_ip": "10.0.1.12",
                "service_name": "h2-api",
            },
            {
                "namespace": "dev",
                "pod_name": "h2-api-def",
                "pod_ip": "10.0.1.13",
                "service_name": "h2-api",
            },
        ],
        controller_tags={},
        cluster_name="H2S-EKS-DEV-STG-EAST-2",
    )

    assert result == {
        "status": "high_confidence",
        "namespace": "dev",
        "service_name": "h2-api",
        "reason": "multi_ip_convergence",
    }


def test_single_ip_with_matching_required_tags_returns_high_confidence() -> None:
    result = evaluate_target_group_enrichment(
        target_type="ip",
        target_ips=["10.0.1.12"],
        matched_pods=[
            {
                "namespace": "dev",
                "pod_name": "h2-api-abc",
                "pod_ip": "10.0.1.12",
                "service_name": "h2-api",
            }
        ],
        controller_tags={
            "elbv2.k8s.aws/cluster": "H2S-EKS-DEV-STG-EAST-2",
            "service.k8s.aws/resource": "service",
            "service.k8s.aws/stack": "dev/h2-api",
        },
        cluster_name="H2S-EKS-DEV-STG-EAST-2",
    )

    assert result == {
        "status": "high_confidence",
        "namespace": "dev",
        "service_name": "h2-api",
        "reason": "single_ip_tag_fallback",
    }


def test_single_ip_without_required_tags_returns_none() -> None:
    result = evaluate_target_group_enrichment(
        target_type="ip",
        target_ips=["10.0.1.12"],
        matched_pods=[
            {
                "namespace": "dev",
                "pod_name": "h2-api-abc",
                "pod_ip": "10.0.1.12",
                "service_name": "h2-api",
            }
        ],
        controller_tags={},
        cluster_name="H2S-EKS-DEV-STG-EAST-2",
    )

    assert result is None


def test_non_ip_target_type_returns_not_applicable() -> None:
    result = evaluate_target_group_enrichment(
        target_type="instance",
        target_ips=[],
        matched_pods=[],
        controller_tags={},
        cluster_name="H2S-EKS-DEV-STG-EAST-2",
    )

    assert result == {
        "status": "not_applicable",
        "reason": "unsupported_target_type",
    }


def test_ambiguous_service_matches_return_none() -> None:
    result = evaluate_target_group_enrichment(
        target_type="ip",
        target_ips=["10.0.1.12", "10.0.1.13"],
        matched_pods=[
            {
                "namespace": "dev",
                "pod_name": "h2-api-abc",
                "pod_ip": "10.0.1.12",
                "service_name": "h2-api",
            },
            {
                "namespace": "dev",
                "pod_name": "h2-api-canary-abc",
                "pod_ip": "10.0.1.13",
                "service_name": "h2-api-canary",
            },
        ],
        controller_tags={},
        cluster_name="H2S-EKS-DEV-STG-EAST-2",
    )

    assert result is None


def test_single_ip_with_conflicting_controller_tags_returns_none() -> None:
    result = evaluate_target_group_enrichment(
        target_type="ip",
        target_ips=["10.0.1.12"],
        matched_pods=[
            {
                "namespace": "dev",
                "pod_name": "h2-api-abc",
                "pod_ip": "10.0.1.12",
                "service_name": "h2-api",
            }
        ],
        controller_tags={
            "elbv2.k8s.aws/cluster": "H2S-EKS-DEV-STG-EAST-2",
            "service.k8s.aws/resource": "service",
            "service.k8s.aws/stack": "dev/h2-api-canary",
        },
        cluster_name="H2S-EKS-DEV-STG-EAST-2",
    )

    assert result is None
