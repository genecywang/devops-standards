"""Canonical resource_type constants and investigation support matrix.

SUPPORT_MATRIX defines which resource types are actively investigated,
which are skipped by design (known but out of scope), and which are
next candidates (planned but not yet implemented).
"""

from enum import Enum


class ResourceType:
    # Kubernetes workloads
    POD = "pod"
    DEPLOYMENT = "deployment"
    STATEFULSET = "statefulset"
    JOB = "job"
    CRONJOB = "cronjob"
    DAEMONSET = "daemonset"
    SERVICE = "service"

    # Kubernetes infrastructure
    NODE = "node"
    NAMESPACE = "namespace"

    # AWS resources
    RDS_INSTANCE = "rds_instance"
    EC2_INSTANCE = "ec2_instance"
    LOAD_BALANCER = "load_balancer"
    TARGET_GROUP = "target_group"
    EKS_CLUSTER = "eks_cluster"
    ELASTICACHE_CLUSTER = "elasticache_cluster"
    MSK_CLUSTER = "msk_cluster"
    SQS_QUEUE = "sqs_queue"
    WAF_WEB_ACL = "waf_web_acl"

    UNKNOWN = "unknown"


# Resource types whose alert_key includes namespace (namespace is part of the unique identity).
NAMESPACE_SCOPED_RESOURCE_TYPES: frozenset[str] = frozenset({
    ResourceType.POD,
    ResourceType.DEPLOYMENT,
    ResourceType.JOB,
    ResourceType.CRONJOB,
    ResourceType.SERVICE,
})


class InvestigationPolicy(Enum):
    INVESTIGATE = "investigate"       # active investigation supported
    NEXT_CANDIDATE = "next_candidate" # planned, not yet implemented — currently skipped
    SKIP = "skip"                     # known type, out of scope by design


# Explicit support matrix — every known resource_type must appear here.
# resource_types absent from this dict are truly unexpected (parser gap or new source).
SUPPORT_MATRIX: dict[str, InvestigationPolicy] = {
    # --- Actively supported ---
    ResourceType.POD: InvestigationPolicy.INVESTIGATE,
    ResourceType.DEPLOYMENT: InvestigationPolicy.INVESTIGATE,
    ResourceType.CRONJOB: InvestigationPolicy.INVESTIGATE,

    # --- Next candidates (planned, not yet implemented) ---
    ResourceType.JOB: InvestigationPolicy.INVESTIGATE,
    ResourceType.STATEFULSET: InvestigationPolicy.NEXT_CANDIDATE,
    ResourceType.DAEMONSET: InvestigationPolicy.NEXT_CANDIDATE,

    # --- Skip by design: Kubernetes workloads without investigation tool ---
    ResourceType.SERVICE: InvestigationPolicy.SKIP,

    # --- Skip by design: Kubernetes infrastructure ---
    # Host-level alerts require node-exporter metrics, not K8s events.
    ResourceType.NODE: InvestigationPolicy.SKIP,
    ResourceType.NAMESPACE: InvestigationPolicy.SKIP,

    # --- Skip by design: AWS resources ---
    # Investigation would require CloudWatch / RDS / EC2 API tools not yet built.
    ResourceType.RDS_INSTANCE: InvestigationPolicy.INVESTIGATE,
    ResourceType.ELASTICACHE_CLUSTER: InvestigationPolicy.INVESTIGATE,
    ResourceType.LOAD_BALANCER: InvestigationPolicy.INVESTIGATE,
    ResourceType.TARGET_GROUP: InvestigationPolicy.INVESTIGATE,
    ResourceType.EC2_INSTANCE: InvestigationPolicy.SKIP,
    ResourceType.EKS_CLUSTER: InvestigationPolicy.SKIP,
    ResourceType.MSK_CLUSTER: InvestigationPolicy.SKIP,
    ResourceType.SQS_QUEUE: InvestigationPolicy.SKIP,
    ResourceType.WAF_WEB_ACL: InvestigationPolicy.SKIP,

    # --- Skip by design: catch-all ---
    ResourceType.UNKNOWN: InvestigationPolicy.SKIP,
}
