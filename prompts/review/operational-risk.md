# Operational Risk Review Prompt

Review the provided OpenSpec artifacts and git diff for operational risk.

Focus on:

- Environment and blast radius.
- Rollback complexity.
- Terraform plan or Helm render evidence.
- Kubernetes dry-run or schema validation evidence.
- Observability and runbook coverage.
- Cost, availability, and scaling impact.

Return findings first, ordered by severity, with file and line references when possible.
