# Design

## Decision

Keep the standards repository as the source of truth. Global templates contain the compact execution contract and skill routing; workflows contain decision tables and evaluation procedures. Update Codex and Claude policy text together, while keeping Codex configuration details product-specific.

The user approved the audit recommendations before implementation. This change records that design and the additional request for a structured prompting framework; it does not add another design-approval pause.

## Superpowers

Use explicit baseline overrides instead of editing the installed third-party bundle or copying its skills into this repository. Universal `using-superpowers` loading is not required. Brainstorming is conditional on ambiguity or consequential alternatives; TDD targets testable behavior and regressions; verification is proportional and evidence-based. Review does not inherently require a subagent. Higher-priority platform instructions still apply, so this policy cannot guarantee that every client will suppress a platform-injected skill.

This retains useful methods without the maintenance cost of a fork. Evaluate a minimal baseline, selected skills, and the full bundle on identical tasks before concluding that a model no longer benefits from scaffolding.

## Planning and authorization

Distinguish execution environment from the target environment affected by the artifact. Local preparation for production is allowed within the user's scope, but production writes still need approval. Small bounded behavior fixes can use a short task record; agent policy, approval, validation semantics, architecture and risky infrastructure changes retain OpenSpec artifacts.

Review outcomes describe readiness (`ready`, `needs changes`, `needs evidence`) and never grant execution permission. Missing deployment approval blocks deployment, not authorized diff/render work. Missing environment/principal information blocks a final safety conclusion, not independent investigation.

## Checker

Add a small Python 3.11+ TOML inspector called by the shell checker. It reads only local config and reports selected hook/skill status without dumping values or parse-error source text. Current `features.hooks` takes precedence over legacy `features.codex_hooks`; comments and strings cannot masquerade as settings. Missing parser support is reported as skipped inspection, never a success claim. This introduces an optional checker dependency, not a bootstrap installation.

Superpowers discovery checks repo `.agents/skills`, user `.agents/skills`, and legacy Codex locations, following directory symlinks. Absence is informational; discovery is not proof of activation. Keep existing sync destinations compatible and avoid duplicate installations.

## Validation and rollback

Use isolated fixtures for config variants, missing/disabled skills, hook JSON and optional discovery; run existing sync regression tests. Review skill scenarios for conceptual questions, typo edits, pending production deployment approval, architecture design, and IAM local preparation. Run strict OpenSpec validation and diff checks. Do not claim these checks prove live Codex/Claude behavior or model performance.

No local config or third-party bundle is rewritten. Reverting the reviewed source diff restores template/skill behavior for newly loaded sessions. Existing sessions may retain prior instructions; start a new session to evaluate adoption.
