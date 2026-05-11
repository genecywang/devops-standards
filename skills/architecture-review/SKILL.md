---
name: architecture-review
description: Use when changes affect cross-module design, platform abstractions, shared interfaces, long-term maintainability, rollback complexity, or architectural trade-offs.
---

# Architecture Review

## Purpose

Review whether a proposed or implemented change is maintainable, bounded, reversible, and aligned with the existing platform architecture.

## Inputs To Read

- Relevant `openspec/changes/<change-id>/proposal.md`, `design.md`, and `tasks.md`.
- Relevant `openspec/specs/**/spec.md`.
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

Decision:
- approve | approve with follow-up | block
```

Severity:

- `critical`: likely outage, irreversible migration, or broad platform breakage.
- `important`: maintainability, rollback, coupling, or migration risk.
- `minor`: readability or local consistency issue.

## Hard Stops

Block the change when:

- No rollback path exists for production or shared-state changes.
- A new abstraction hides operational behavior or security boundaries.
- Design contradicts OpenSpec requirements.
- The change expands blast radius without explicit justification.
