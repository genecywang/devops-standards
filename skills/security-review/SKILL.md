---
name: security-review
description: Use when a change alters permissions, trust boundaries, secret handling, network exposure, or security controls such as IAM, RBAC, KMS, and CI tokens. Excludes conceptual explanations and wording-only edits.
---

# Security Review

## Purpose

Review security-sensitive changes for least privilege, credential safety, trust boundaries, and privilege escalation paths.

Read only relevant available artifacts. Local policy editing and static validation can proceed within the user's scope without AWS write approval. Identify execution environment separately from the target environment and principal; unresolved targets prevent a final safety conclusion, not independent local investigation.

## Inputs To Read

- Available task requirements, design decisions, and issue/PR context.
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

Review readiness:
- ready | needs changes | needs evidence
```

Severity:

- `critical`: secret exposure, privilege escalation, public access, production-impacting permission expansion.
- `important`: broad permissions, missing conditions, weak trust boundary, insufficient rollback.
- `minor`: naming, documentation, or defense-in-depth improvement.

## Readiness and Authorization

Report `needs changes` or `needs evidence` before recommending merge or execution when:

- Secrets or credentials would be printed, committed, or exposed.
- IAM / RBAC expands privilege without justification.
- Production security controls are weakened without approval.
- The review cannot identify the target environment or principal.

Never print, commit, or expose secrets. Do not access credentials or mutate permissions without required human approval. Continue safe local preparation while approval is pending; review readiness does not grant execution permission. State which action is blocked and why, rather than blocking the entire task.

JSON parsing and wildcard scans are limited evidence, not proof of least privilege or correct effective permissions. Disclose missing semantic review or unavailable policy-analysis tooling.
