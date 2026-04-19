from __future__ import annotations


def evaluate_target_group_enrichment(
    *,
    target_type: str,
    target_ips: list[str],
    matched_pods: list[dict[str, str]],
    controller_tags: dict[str, str],
    cluster_name: str,
) -> dict[str, str] | None:
    if target_type != "ip":
        return {
            "status": "not_applicable",
            "reason": "unsupported_target_type",
        }

    unique_target_ips = {ip for ip in target_ips if ip}
    matched_ip_to_service = {
        pod["pod_ip"]: (pod["namespace"], pod["service_name"])
        for pod in matched_pods
        if pod.get("pod_ip") and pod.get("namespace") and pod.get("service_name")
    }
    unique_services = set(matched_ip_to_service.values())

    if len(unique_target_ips) >= 2 and len(matched_ip_to_service) >= 2 and len(unique_services) == 1:
        namespace, service_name = next(iter(unique_services))
        return {
            "status": "high_confidence",
            "namespace": namespace,
            "service_name": service_name,
            "reason": "multi_ip_convergence",
        }

    if len(unique_target_ips) == 1 and len(matched_ip_to_service) == 1 and len(unique_services) == 1:
        namespace, service_name = next(iter(unique_services))
        if _controller_tags_match(controller_tags, cluster_name, namespace, service_name):
            return {
                "status": "high_confidence",
                "namespace": namespace,
                "service_name": service_name,
                "reason": "single_ip_tag_fallback",
            }

    return None


def _controller_tags_match(
    controller_tags: dict[str, str],
    cluster_name: str,
    namespace: str,
    service_name: str,
) -> bool:
    return (
        controller_tags.get("elbv2.k8s.aws/cluster") == cluster_name
        and controller_tags.get("service.k8s.aws/resource") == "service"
        and controller_tags.get("service.k8s.aws/stack") == f"{namespace}/{service_name}"
    )
