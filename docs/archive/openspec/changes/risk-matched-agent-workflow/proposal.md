# Why

Global conditional-skill guidance conflicts with universal Superpowers gates. Small changes can acquire unnecessary planning, approval, and verification work. The setup checker also assumes a specific optional-skill location and a deprecated Codex hook flag.

# What Changes

- Define bounded local execution and risk-matched planning/verification in both agent templates.
- Treat Superpowers as an optional toolbox, with explicit user-level overrides for universal loading, brainstorming, TDD, repeated validation, and mandatory delegation.
- Separate review readiness from authorization to mutate external state.
- Accept current and legacy hook settings using TOML parsing; report optional Superpowers discovery without requiring it.
- Add structured task prompts and an evaluation guide for GPT-6 models and Superpowers.
- Define automatic task structuring in both global baselines so new sessions need no template path or user-filled form.

# Capabilities

## Modified Capabilities

- `ai-coding-workflow`: planning scope, conditional skills, validation scope, setup checks, and task contracts.

# Impact

- Execution environment: local. Target: agent workflow standards, templates, review skills, setup tooling.
- Blast radius: this repository and consumer sessions that adopt it; existing personal instruction/skill symlinks read the updated source.
- Security/operational risk: accidentally relaxing write authorization. Existing production/shared, IAM, secret, destructive-operation gates remain unchanged.
- Rollback: restore the changed tracked files from the pre-change revision after review; no cloud/state migration is involved.
- Observability: deterministic checker tests, recorded scenario review, and validation evidence.
- Out of scope: model default changes, third-party package edits, cloud operations, credentials, global config mutation, installation, commit/push, and automated multi-model benchmarks.
