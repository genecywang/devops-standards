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

The repository SHALL use OpenSpec for agent policy, approval gates, validation semantics, cross-module design, and risky infrastructure changes. Small, bounded behavior fixes MAY use a short intent, scope, and verification record unless local rules require OpenSpec.

#### Scenario: Workflow policy changes

- GIVEN a change alters agent behavior or authorization semantics
- WHEN implementation begins
- THEN an OpenSpec proposal, specs, design, and tasks SHALL exist

#### Scenario: Bounded local fix

- GIVEN a fix has clear requirements, limited scope, no interface or permission change, and no significant operational risk
- WHEN the agent implements it
- THEN it MAY proceed with a short task record and relevant verification without a new OpenSpec change

### Requirement: Conditional skill loading

The repository SHALL select skills by task intent and semantic impact, not keywords alone. Superpowers SHALL be optional; user baseline rules SHALL override conflicting skill guidelines without overriding platform permissions.

#### Scenario: Conceptual question or typo

- GIVEN a task explains IAM concepts or fixes a Helm README typo
- WHEN the agent selects skills
- THEN it SHALL NOT require a domain change review solely because those technology names appear

#### Scenario: Explicit bounded implementation

- GIVEN the user has authorized a clear local task
- WHEN a generic skill requires universal brainstorming, design approval, or mandatory delegation
- THEN the agent SHALL apply the baseline's conditional triggers and continue authorized work

#### Scenario: Security or operational semantics change

- GIVEN a change modifies permissions, trust boundaries, infrastructure behavior, or deploy/rollback paths
- WHEN preparing or reviewing it
- THEN the agent SHALL use the relevant domain review skill

### Requirement: Human approval for shared-state writes

The repository SHALL prevent AI agents from autonomously performing operations that mutate production or shared infrastructure state. Explicit approval SHALL cover the exact target and scope; an existing valid approval SHALL NOT require repeated confirmation for that same operation.

#### Scenario: Terraform apply is needed

- GIVEN implementation requires `terraform apply` and no explicit approval covers that target and scope
- WHEN the agent reaches execution
- THEN it SHALL stop before the write
- AND it SHALL explain the risk and impact scope
- AND it SHALL wait for explicit human approval while continuing independent authorized local preparation

#### Scenario: Local validation is needed

- GIVEN implementation requires lint, test, render, dry-run, or static validation
- WHEN the command is local and non-destructive
- THEN the agent MAY run it without additional approval

### Requirement: Evidence before completion

The repository SHALL require relevant validation evidence before completion claims, commits, or PR handoff. Verification SHALL match the change's risk and SHALL NOT be broadened or repeated without a new change, failure, or unresolved concern.

#### Scenario: Relevant checks pass

- GIVEN checks cover the changed behavior and required project checks pass
- WHEN no new code or unresolved concern invalidates the evidence
- THEN the agent SHALL proceed to delivery without repeating unrelated checks

#### Scenario: Validation is unavailable or limited

- GIVEN a tool is missing or a check only validates syntax
- WHEN the agent reports results
- THEN it SHALL disclose the skipped check or limitation rather than claim semantic safety

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

### Requirement: Preparation and authorization are distinct

The agent SHALL distinguish execution environment, target environment, review readiness, and human execution approval. Existing approval-required operations SHALL remain gated.

#### Scenario: Local production artifact preparation

- GIVEN the user authorizes a local chart or IAM policy change without deployment approval
- WHEN the agent prepares a diff and static validation
- THEN it SHALL continue the authorized preparation
- AND it SHALL wait for explicit approval before any gated external mutation
- AND a review's ready conclusion SHALL NOT grant that approval

### Requirement: Setup inspection is compatible and non-destructive

The checker SHALL parse TOML settings, recognize current and legacy hook keys, treat Superpowers as optional, and avoid exposing unrelated configuration values.

#### Scenario: Current hook setting exists

- GIVEN local config enables `features.hooks`
- WHEN setup is checked
- THEN the checker SHALL report the local hook flag as enabled
- AND an explicit current flag SHALL take precedence over the legacy alias

#### Scenario: Optional bundle is absent

- GIVEN Superpowers is absent or installed via a supported alternative discovery path
- WHEN setup is checked
- THEN absence SHALL NOT cause a missing-dependency warning or failure
- AND a discovered path SHALL NOT be described as proof of activation

#### Scenario: Config cannot be parsed

- GIVEN Python TOML support is unavailable or config is invalid
- WHEN setup is checked
- THEN inspection SHALL be reported as skipped or failed without printing config contents

### Requirement: Outcome-based task contracts and evaluation

The repository SHALL provide reusable prompts describing goals, relevant context, constraints, deliverables, and observable completion criteria. Infrastructure tasks SHALL identify execution and target environments and authorization boundaries.

#### Scenario: Structured prompt adoption

- GIVEN a user selects a task template
- WHEN completing its fields
- THEN unnecessary fields MAY be omitted and routine execution steps SHALL remain agent decisions
- AND source material SHALL be distinguished from instructions


#### Scenario: Global baseline structures a new task

- GIVEN a new session loads the global baseline and receives a multi-step development, infrastructure, incident, or review task
- WHEN the user describes the task in natural language
- THEN the agent SHALL organize the goal, relevant context, constraints, deliverable, and completion criteria from available information
- AND infrastructure tasks SHALL distinguish execution environment, target environment, and authorization
- AND the agent SHALL ask only about consequential missing information without inventing authorization
- AND it SHALL NOT require a user-filled template, a template file path, or an extra approval gate for a clear authorized task
- AND simple questions, typo fixes, and formatting-only edits SHALL NOT require the full structure
- AND the structure need not be displayed unless useful to clarify scope

#### Scenario: Model or Superpowers comparison

- GIVEN a proposed model, reasoning, or skill-policy change
- WHEN evaluating it
- THEN representative tasks SHALL compare quality, intervention, time, and boundary compliance while changing one factor at a time
- AND unperformed evaluations SHALL NOT be reported as measured improvements

### Requirement: Legacy setup guidance does not override task authorization

Setup documentation SHALL describe explicit adoption scope and SHALL NOT treat reading a document as permission to change global settings, enable permission bypass, or install unrelated packages. Optional skills SHALL NOT be reported as required dependencies solely because they appear in a static catalog.

#### Scenario: User reads setup documentation

- GIVEN a user or agent reads a setup guide
- WHEN no installation or global configuration change has been requested
- THEN the guide SHALL NOT instruct the agent to execute global writes automatically

#### Scenario: Existing installer hook remains configured

- GIVEN a user settings file still references `skills/install-skills/check-skills.sh`
- WHEN the hook runs after catalog retirement
- THEN it SHALL exit successfully without output, installation, or configuration mutation

#### Scenario: User requests a specific skill

- GIVEN the user explicitly requests a skill installation
- WHEN the installer prepares it
- THEN it SHALL verify the requested source and destination and limit changes to the authorized scope
- AND it SHALL NOT install all previously cataloged packages or infer approval to overwrite existing files
