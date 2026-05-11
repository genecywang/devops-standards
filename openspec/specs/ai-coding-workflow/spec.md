# ai-coding-workflow Specification

## Purpose

Define a Codex-first, Claude Code-compatible standards system for DevOps and Platform Engineering AI-assisted work. This repository stores reusable templates, workflow specs, conditional skills, and validation scripts; consumer repositories should adopt and review the pieces they need.

## Requirements

### Requirement: Standards source of truth

The repository SHALL act as the source of truth for reusable AI workflow standards, not as the consumer project being operated.

#### Scenario: Agent maintains this repository

- GIVEN Codex or Claude Code starts in this repository
- WHEN it reads repo guidance
- THEN it SHALL treat root `AGENTS.md` and `CLAUDE.md` as maintenance instructions for this standards repository
- AND it SHALL not assume this repository is the target infrastructure system

#### Scenario: Consumer repository adopts the standards

- GIVEN another repository wants to use this workflow
- WHEN templates or scripts are copied into that repository
- THEN the target repository SHALL review and own its project-local instructions, validation commands, and production approval gates

### Requirement: Dual agent entry points

The repository SHALL provide separate entry-point instruction files and reusable global templates for Codex and Claude Code while keeping both aligned to the same workflow and safety model.

#### Scenario: Codex starts in the repository

- GIVEN Codex starts in this repository
- WHEN it loads project guidance
- THEN it SHALL use root `AGENTS.md` as the standards-repository maintenance entry point
- AND it MAY use `templates/codex/AGENTS.global.md` as the global baseline template

#### Scenario: Claude Code starts in the repository

- GIVEN Claude Code starts in this repository
- WHEN it loads project guidance
- THEN it SHALL use root `CLAUDE.md` as the standards-repository maintenance entry point
- AND it MAY use `templates/claude/CLAUDE.global.md` as the global baseline template

### Requirement: Personal global sync is explicit and reversible

The repository SHALL provide a personal fast-sync path that links global Codex and Claude Code instruction files to versioned templates without silently overwriting local files.

#### Scenario: Personal sync runs on a clean machine

- GIVEN `~/.codex/AGENTS.md` and `~/.claude/CLAUDE.md` do not exist
- WHEN `scripts/sync-personal-ai-config.sh` runs
- THEN it SHALL create symlinks to `templates/codex/AGENTS.global.md` and `templates/claude/CLAUDE.global.md`
- AND it SHALL create namespaced Codex skill symlinks under `~/.codex/skills/`

#### Scenario: Existing global instruction file is present

- GIVEN a destination file already exists
- WHEN `scripts/sync-personal-ai-config.sh` runs without `--force`
- THEN it SHALL stop without modifying the existing file
- AND it SHALL tell the user to rerun with `--force` only after reviewing impact

#### Scenario: Force sync replaces an existing destination

- GIVEN a destination file already exists
- WHEN `scripts/sync-personal-ai-config.sh --force` runs
- THEN it SHALL move the existing destination to `.bak.<timestamp>`
- AND it SHALL create the requested symlink

### Requirement: OpenSpec as planning layer

The repository SHALL use OpenSpec to capture intent, requirements, design decisions, and tasks for meaningful workflow or infrastructure changes.

#### Scenario: Risky infrastructure change is requested

- GIVEN a requested change affects Terraform, Kubernetes, Helm, AWS, IAM, CI/CD, or observability
- WHEN the change is multi-step or affects operational behavior
- THEN an OpenSpec change SHALL be created or updated before implementation
- AND the change SHALL include proposal, specs, design, and tasks artifacts

#### Scenario: Small documentation correction is requested

- GIVEN a requested change only fixes typos, formatting, or non-behavioral documentation
- WHEN no workflow or operational semantics change
- THEN the agent MAY edit directly
- AND it SHALL still verify the resulting diff before claiming completion

### Requirement: Conditional skill loading

The repository SHALL prefer conditional skill loading over always-on heavyweight skill context.

#### Scenario: Security-sensitive change is requested

- GIVEN a change touches IAM, RBAC, secrets, credentials, network policy, KMS, S3 policy, or CI tokens
- WHEN the agent plans or reviews the change
- THEN it SHALL use the security review skill

#### Scenario: Operational-risk change is requested

- GIVEN a change touches Terraform, Helm, Kubernetes, AWS writes, production, staging, or shared state
- WHEN the agent plans or reviews the change
- THEN it SHALL use the operational risk review skill

### Requirement: Human approval for shared-state writes

The repository SHALL prevent AI agents from autonomously performing operations that mutate production or shared infrastructure state.

#### Scenario: Terraform apply is needed

- GIVEN implementation requires `terraform apply`
- WHEN the agent reaches that step
- THEN it SHALL stop
- AND it SHALL explain the risk and impact scope
- AND it SHALL wait for explicit human approval

#### Scenario: Local validation is needed

- GIVEN implementation requires lint, test, render, dry-run, or static validation
- WHEN the command is local and non-destructive
- THEN the agent MAY run it without additional approval

### Requirement: Evidence before completion

The repository SHALL require fresh validation evidence before completion claims, commits, or PR handoff.

#### Scenario: Agent claims work is complete

- GIVEN the agent is about to claim completion
- WHEN validation commands exist for the changed area
- THEN the agent SHALL run the relevant commands
- AND it SHALL report actual results, including skipped checks and reasons

### Requirement: Bootstrap is explicit and reviewable

The repository SHALL provide a Codex bootstrap path for this standards repository that can check setup automatically but installs global tools only after explicit user action.

#### Scenario: New Codex session starts

- GIVEN Codex starts in this repository with the repo-local config enabled
- WHEN the `SessionStart` hook runs
- THEN it SHALL run a non-destructive setup check
- AND it SHALL not install OpenSpec or modify global environment state

#### Scenario: User approves OpenSpec installation

- GIVEN OpenSpec is missing
- WHEN the user explicitly runs `scripts/bootstrap-codex-workflow.sh --install-openspec`
- THEN the script MAY install OpenSpec with `npm install -g @fission-ai/openspec@latest`
- AND it SHALL run repository validation after setup
