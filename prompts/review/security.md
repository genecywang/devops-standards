# Security Review Prompt

Review the provided OpenSpec artifacts and git diff for security risk.

Focus on:

- Least privilege.
- IAM / RBAC wildcard expansion.
- Trust policy and OIDC subjects.
- Secret and credential handling.
- CI/CD token scope.
- Network exposure.

Return findings first, ordered by severity, with file and line references when possible.
