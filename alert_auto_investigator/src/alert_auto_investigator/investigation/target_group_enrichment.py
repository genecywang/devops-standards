from __future__ import annotations

from alert_auto_investigator.models.normalized_alert_event import NormalizedAlertEvent


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


def enrich_target_group_response(
    *,
    alert: NormalizedAlertEvent,
    response: object,
    kubernetes_adapter: object | None,
    allowed_namespaces: list[str],
) -> dict[str, str] | None:
    if kubernetes_adapter is None or not allowed_namespaces:
        return None

    evidence = getattr(response, "evidence", []) or []
    if not evidence or not isinstance(evidence[0], dict):
        return None

    payload = evidence[0]
    target_type = str(payload.get("target_type") or "")
    target_ips = [str(ip) for ip in payload.get("target_ips", []) if str(ip)]
    controller_tags = {
        str(key): str(value)
        for key, value in ((payload.get("k8s_controller_tags") or {}).items())
        if str(key) and str(value)
    }

    matched_pods: list[dict[str, str]] = []
    for target_ip in target_ips:
        pod = kubernetes_adapter.find_pod_by_ip(alert.cluster, allowed_namespaces, target_ip)
        if pod is None:
            continue

        namespace = str(pod.get("namespace") or "")
        pod_name = str(pod.get("pod_name") or "")
        if not namespace or not pod_name:
            continue

        service = kubernetes_adapter.find_service_for_pod(
            alert.cluster,
            allowed_namespaces,
            namespace,
            pod_name,
        )
        if service is None:
            continue

        service_name = str(service.get("service_name") or "")
        if not service_name:
            continue

        matched_pods.append(
            {
                "namespace": namespace,
                "pod_name": pod_name,
                "pod_ip": target_ip,
                "service_name": service_name,
            }
        )

    cluster_name = alert.cluster.strip() or str(controller_tags.get("elbv2.k8s.aws/cluster") or "")
    enrichment = evaluate_target_group_enrichment(
        target_type=target_type,
        target_ips=target_ips,
        matched_pods=matched_pods,
        controller_tags=controller_tags,
        cluster_name=cluster_name,
    )
    if enrichment is None or enrichment.get("status") != "high_confidence":
        return None

    return {
        "confidence": "high",
        "namespace": enrichment["namespace"],
        "service_name": enrichment["service_name"],
        "reason": enrichment["reason"],
    }


def _controller_tags_match(
    controller_tags: dict[str, str],
    cluster_name: str,
    namespace: str,
    service_name: str,
) -> bool:
    cluster_tag = controller_tags.get("elbv2.k8s.aws/cluster")
    return (
        bool(cluster_tag)
        and (not cluster_name or cluster_tag == cluster_name)
        and controller_tags.get("service.k8s.aws/resource") == "service"
        and controller_tags.get("service.k8s.aws/stack") == f"{namespace}/{service_name}"
    )
