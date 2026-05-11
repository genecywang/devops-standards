---
name: security-review
description: Use when changes touch IAM, RBAC, secrets, credentials, KMS, S3 policy, network policy, CI tokens, authn/authz, or security-sensitive automation.
---

# Security Review

## Purpose

Review security-sensitive changes for least privilege, credential safety, trust boundaries, and privilege escalation paths.

## Inputs To Read

- Relevant OpenSpec proposal, design, tasks, and specs.
- Git diff or changed files.
- IAM / RBAC / policy JSON / CI config being changed.
- Existing policy patterns in the repository.

## Review Focus

- Least privilege: wildcard actions, wildcard resources, missing conditions.
- Trust boundary: principals, service accounts, OIDC subjects, external accounts.
- Secret handling: no secret output, no hardcoded credentials, no unsafe debug logs.
- CI/CD credentials: scoped tokens, protected branches, approval gates.
- Network exposure: ingress, security groups, network policies, public access.
- Rollback: can access be revoked safely and quickly?

## Output Format

```text
Security review:

Findings:
- [severity] file/path:line - issue, exploit path or exposure, recommended change

Required approvals:
- human approval needed for ...

Decision:
- approve | approve with follow-up | block
```

Severity:

- `critical`: secret exposure, privilege escalation, public access, production-impacting permission expansion.
- `important`: broad permissions, missing conditions, weak trust boundary, insufficient rollback.
- `minor`: naming, documentation, or defense-in-depth improvement.

## Hard Stops

Block the change when:

- Secrets or credentials would be printed, committed, or exposed.
- IAM / RBAC expands privilege without justification.
- Production security controls are weakened without approval.
- The review cannot identify the target environment or principal.
