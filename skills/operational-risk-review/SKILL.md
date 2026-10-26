---
name: operational-risk-review
description: Use when a change alters infrastructure behavior, deploy/rollback paths, availability, observability, or blast radius in Terraform, Helm, Kubernetes, or AWS. Excludes conceptual questions, typo edits, and formatting-only changes.
---

# Operational Risk Review

## Purpose

Review operational risk before implementation, merge, deployment, or archive. Focus on blast radius, rollback complexity, validation evidence, and observability.

Match the review to its stage. Before implementation, identify required evidence; after implementation, inspect the relevant results. Do not demand a completed plan/render before allowing the local edits needed to produce it. Read only relevant available artifacts.

## Inputs To Read

- Available task requirements, design decisions, and issue/PR context.
- Git diff or changed files.
- Terraform plan, Helm render, Kubernetes dry-run, or CI output when available.
- Runbooks, dashboards, alerts, or validation scripts referenced by the change.

## Review Focus

- Execution environment and target environment: local, CI, staging, production, or shared; local chart editing for production is not a deployment.
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

Review readiness:
- ready | needs changes | needs evidence

Execution approval:
- gated action and whether human authorization exists for its target/scope
```

Severity:

- `critical`: likely outage, irreversible state/data loss, missing production rollback.
- `important`: incomplete validation, unclear blast radius, weak observability.
- `minor`: documentation or follow-up improvement.

## Readiness and Authorization

Report `needs changes` or `needs evidence` before recommending merge or execution when:

- Rollback path is missing for a risky change.
- Terraform / Helm / Kubernetes change lacks plan, render, or static validation evidence.
- Observability is missing for a change that can fail after deploy.

Missing deployment approval blocks the actual production/shared-state write, not authorized local diff, render, or rollback preparation. Planning an operation does not authorize it. A `ready` review is not human approval; preserve all existing Terraform, Kubernetes, Helm, AWS, credential, and destructive-operation gates.

Use evidence appropriate to the change and available environment. Do not access credentials or run remote operations just to fill a checklist. Report skipped validation and its implications; once required checks pass, expand or repeat them only for new changes, failures, or unresolved concerns.
