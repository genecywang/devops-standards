# AI Coding Workflow

## Default Flow

```text
proposal -> specs -> design -> tasks -> implementation -> validation -> review -> archive
```

## Modes

| Mode | Use When | Required Artifacts |
|---|---|---|
| Quick edit | typo, formatting, non-behavioral docs | git diff only |
| Standard change | behavior, workflow, automation, infra logic | OpenSpec proposal, specs, design, tasks |
| High-risk change | production, shared state, IAM, RBAC, cluster writes | OpenSpec artifacts, validation evidence, human approval |
| Incident/debug | failures, broken CI, unexpected behavior | symptoms, evidence, hypothesis, verification, fix, rollback |

## Agent Responsibilities

| Layer | Owner | Responsibility |
|---|---|---|
| Intent | OpenSpec | why, what, scope, requirements, design, tasks |
| Execution | Codex / Claude Code | local edits, tests, static validation, diff, commit |
| Review | Skills / reviewer | architecture, security, operational risk |
| Approval | Human | production, shared-state, secret, IAM, destructive operations |

## Repository Roles

| Location | Role |
|---|---|
| Root `AGENTS.md` / `CLAUDE.md` | Maintaining this standards repository |
| `templates/codex/AGENTS.global.md` | Personal global Codex baseline |
| `templates/claude/CLAUDE.global.md` | Personal global Claude Code baseline |
| Consumer repo `AGENTS.md` / `CLAUDE.md` | Target repo-specific deploy, validation, and approval rules |

## Standard Change Procedure

1. Read the active `AGENTS.md` or `CLAUDE.md`.
2. Read relevant `openspec/specs/**/spec.md`.
3. Create or update `openspec/changes/<change-id>/`.
4. Confirm proposal and tasks are reviewable.
5. Implement one bounded task at a time.
6. Run relevant `validations/*.sh`.
7. Run conditional review skills when triggered.
8. Commit only after validation evidence is available.
9. Archive OpenSpec change after implemented behavior is accepted.

## Context Hygiene

- Keep entry-point instructions short.
- Put durable behavior in `openspec/specs/`.
- Put detailed procedures in `workflows/`.
- Put judgment-heavy checklists in conditional `skills/`.
- Put deterministic checks in `validations/`.

## When To Stop

Stop and ask for approval when a step requires:

- Terraform apply, destroy, import, or state mutation.
- Kubernetes write operation.
- Helm release mutation.
- AWS write operation.
- Secret or credential access.
- Production or shared environment deploy / rollback.
