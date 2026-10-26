---
name: architecture-review
description: Use when a change alters cross-module boundaries, shared interfaces, platform abstractions, or complex migration design. Excludes conceptual questions and wording-only edits.
---

# Architecture Review

## Purpose

Review whether a proposed or implemented change is maintainable, bounded, reversible, and aligned with the existing platform architecture.

Review only the affected decisions. Read available relevant artifacts; do not require a particular planning tool or document bundle. During design, missing information is an open question to investigate, not a reason to stop all local preparation.

## Inputs To Read

- Available task requirements, design decisions, issue/PR context, and applicable repository rules.
- Git diff or changed files.
- Existing local patterns before proposing new abstractions.

## Review Focus

- Boundary clarity: modules, ownership, inputs, outputs, dependencies.
- Maintainability: complexity, naming, duplication, future change cost.
- Operational fit: rollback path, migration path, observability, failure modes.
- Blast radius: shared components, production impact, coupling to global state.
- YAGNI: avoid frameworks, agents, or abstractions without concrete need.

## Output Format

```text
Architecture review:

Findings:
- [severity] file/path:line - issue, impact, recommended change

Open questions:
- question or assumption

Review readiness:
- ready | needs changes | needs evidence
```

Severity:

- `critical`: likely outage, irreversible migration, or broad platform breakage.
- `important`: maintainability, rollback, coupling, or migration risk.
- `minor`: readability or local consistency issue.

## Readiness and Authorization

Report `needs changes` or `needs evidence` before recommending merge or execution when:

- No rollback path exists for production or shared-state changes.
- A new abstraction hides operational behavior or security boundaries.
- Design contradicts the agreed requirements.
- The change expands blast radius without explicit justification.

State the affected stage and what would resolve each finding. Continue authorized local investigation and corrections. A `ready` review never authorizes a deploy, state mutation, or other gated action; obtain human approval immediately before that action if it has not already been granted for that scope.
