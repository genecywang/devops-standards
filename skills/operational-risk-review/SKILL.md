---
name: operational-risk-review
description: Use when changes affect Terraform, Helm, Kubernetes, AWS resources, production or shared environments, deploy/rollback paths, observability, or blast radius.
---

# Operational Risk Review

## Purpose

Review operational risk before implementation, merge, deployment, or archive. Focus on blast radius, rollback complexity, validation evidence, and observability.

## Inputs To Read

- Relevant OpenSpec proposal, design, tasks, and specs.
- Git diff or changed files.
- Terraform plan, Helm render, Kubernetes dry-run, or CI output when available.
- Runbooks, dashboards, alerts, or validation scripts referenced by the change.

## Review Focus

- Environment: local, CI, staging, production, or shared.
- Blast radius: accounts, clusters, namespaces, regions, tenants, services.
- Rollback: command path, data/state reversibility, time to recover.
- Validation: plan/render/static checks, test coverage, dry-run evidence.
- Observability: metrics, logs, alerts, dashboards, runbooks.
- Cost and availability: multi-AZ, scaling, quotas, noisy neighbor risk.

## Output Format

```text
Operational risk review:

Risk summary:
- environment:
- blast radius:
- rollback complexity:
- validation evidence:

Findings:
- [severity] file/path:line - issue, operational impact, recommended change

Decision:
- approve | approve with follow-up | block
```

Severity:

- `critical`: likely outage, irreversible state/data loss, missing production rollback.
- `important`: incomplete validation, unclear blast radius, weak observability.
- `minor`: documentation or follow-up improvement.

## Hard Stops

Block the change when:

- Production or shared-state writes are planned without human approval.
- Rollback path is missing for a risky change.
- Terraform / Helm / Kubernetes change lacks plan, render, or static validation evidence.
- Observability is missing for a change that can fail after deploy.
