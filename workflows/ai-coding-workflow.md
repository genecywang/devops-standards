# AI Coding Workflow

Use the amount of planning needed to make the task and its risks clear. No specific planning tool, document bundle, or archive ceremony is required. A conversation, issue, PR, or focused design note can carry the relevant decisions.

## Modes

| Mode | Use When | Required Artifacts |
|---|---|---|
| Quick edit | typo, formatting, non-behavioral docs | git diff only |
| Bounded fix | clear local behavior fix with no interface/permission change or significant operational risk | short intent, scope, relevant verification, diff |
| Standard change | agent policy, approval/validation semantics, cross-module design, significant automation or infra behavior | reviewable intent, scope, consequential decisions, and verification approach |
| High-risk change | production/shared-state risk, permission or trust changes, cluster writes | risk/rollback notes, validation evidence; human approval before gated execution |
| Incident/debug | failures, broken CI, unexpected behavior | symptoms, evidence, hypothesis, verification, fix, rollback |

## Agent Responsibilities

| Layer | Owner | Responsibility |
|---|---|---|
| Intent | User and agent | why, what, scope, requirements, design, tasks |
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

## Execution Guidance

Read applicable repository instructions and the context relevant to the task. Resolve consequential ambiguity, then complete authorized edits and required verification. Use focused review where the changed behavior warrants it; do not add approval pauses for decisions already authorized by the user.

Record intent, scope, important decisions, and evidence in the conversation, issue, PR, or a design note proportionate to risk. Small fixes need only a brief record and relevant checks. No separate planning artifacts or archive step are mandatory. Split execution environment from target environment: local preparation of a production artifact is not a deployment. Continue independent authorized work while a question is pending. Commit only after relevant validation and within the requested scope.

## Skill Selection

Superpowers is optional. Apply the explicit routing overrides in the global baseline: no universal entry skill, no design approval for an already clear task, and no mandatory delegation merely to perform review. Use brainstorming for meaningful ambiguity, debugging for actual failures, and TDD for testable logic/regressions. Domain reviews follow semantic impact, not technology keywords. A short skill does not need extra reference files just to use progressive disclosure.

See [model and skill evaluation](model-skill-evaluation.md) when changing model, reasoning effort, or skill policy; do not load the evaluation guide on ordinary coding tasks.

## Risk-Matched Verification

| Change | Relevant evidence |
|---|---|
| Typo / formatting | Diff; formatter check if applicable |
| Executable logic / regression | Affected tests and a regression reproducer when practical |
| Declarative configuration | Render, schema/static validation, and semantic diff as applicable |
| Infrastructure / security behavior | Required project checks plus relevant plan/render/policy review; disclose missing environment-dependent checks |
| Agent policy / approval / validation semantics | requirements consistency, representative behavior scenarios, applicable tooling tests, boundary review |

Do not add tests that only mirror wording or implementation. Complete required checks, then stop testing unless a new edit, failure, or unresolved concern changes the evidence. Report exact scope and skipped checks. `validations/all.sh` runs all supported infra checks; use it for relevant multi-type changes, not every task. `validations/iam.sh` only parses JSON and warns about selected wildcards; it does not prove policy safety or effective permissions.

## Review Readiness

Use `ready`, `needs changes`, or `needs evidence` to describe the reviewed artifact and its stage. A readiness conclusion is not human execution approval. Missing deployment approval blocks deployment; it does not block authorized local editing, static validation, or rollback preparation. Missing evidence during design becomes a concrete follow-up, not a blanket stop.

## Context Hygiene

- Keep entry-point instructions short.
- Keep current requirements in applicable repository instructions and focused workflow documentation. Historical archives are not active instructions.
- Put detailed procedures in `workflows/`.
- Put judgment-heavy checklists in conditional `skills/`.
- Put deterministic checks in `validations/`.

## When To Stop

Before executing any operation below, stop and ask for approval unless explicit human approval already covers that exact target and scope. Continue independent authorized local preparation while approval is pending:

- Terraform apply, destroy, import, or state mutation.
- Kubernetes write operation.
- Helm release mutation.
- AWS write operation.
- Secret or credential access.
- Production or shared environment deploy / rollback.
