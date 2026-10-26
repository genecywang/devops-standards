# infra-change-management Specification

## Purpose

Define how AI agents plan, implement, validate, and review DevOps / Platform Engineering changes across Terraform, Kubernetes, Helm, Jenkins, AWS IAM, observability, CI/CD, and platform tooling.

## Requirements

### Requirement: Environment and target classification

Every infrastructure change SHALL identify the environment level and target system before analysis or implementation.

#### Scenario: Environment is not provided

- GIVEN the user asks for an infrastructure change
- WHEN the environment is not stated
- THEN the agent SHALL ask or infer only from repo-local evidence
- AND it SHALL not assume production

#### Scenario: Production is confirmed

- GIVEN the target environment is production
- WHEN the agent proposes or reviews a change
- THEN it SHALL include cost, availability, multi-AZ, rollback, blast radius, security, and observability considerations

### Requirement: Terraform safety

Terraform work SHALL separate planning from applying.

#### Scenario: Terraform code changes

- GIVEN Terraform files are changed
- WHEN validation is performed
- THEN the agent SHALL run formatting and static validation where tools are available
- AND it MAY run `terraform plan`
- AND it SHALL not run `terraform apply`, `destroy`, `state mv`, or `state rm` without explicit approval

### Requirement: Kubernetes and Helm safety

Kubernetes and Helm work SHALL validate rendered resources before cluster writes.

#### Scenario: Helm chart changes

- GIVEN Helm chart files are changed
- WHEN validation is performed
- THEN the agent SHALL run `helm lint`
- AND it SHOULD render manifests with `helm template`
- AND it SHALL not run `helm upgrade`, `install`, `uninstall`, or `rollback` without explicit approval

#### Scenario: Kubernetes manifest changes

- GIVEN Kubernetes YAML is changed
- WHEN validation is performed
- THEN the agent SHOULD run schema validation with `kubeconform` or `kubectl --dry-run=client`
- AND it SHALL not run `kubectl apply`, `delete`, `edit`, `patch`, or `rollout` without explicit approval

### Requirement: IAM and security review

IAM and security-sensitive changes SHALL receive focused review for least privilege and credential safety.

#### Scenario: IAM policy changes

- GIVEN a policy or trust relationship changes
- WHEN review is performed
- THEN the review SHALL inspect wildcard actions, wildcard resources, trust principals, conditions, privilege escalation paths, and rollback complexity

### Requirement: Observability and rollback

Operational changes SHALL define how failure will be detected and how rollback will be performed.

#### Scenario: Workload behavior changes

- GIVEN a workload, deployment, autoscaling, logging, or alerting behavior changes
- WHEN design is written
- THEN it SHALL identify metrics, logs, alerts, dashboards, or runbook updates needed to operate the change
- AND it SHALL define rollback steps or explicitly state why rollback is not applicable
