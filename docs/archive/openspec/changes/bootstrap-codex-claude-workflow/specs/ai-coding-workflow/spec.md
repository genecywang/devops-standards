# ai-coding-workflow Delta Specification

## ADDED Requirements

### Requirement: Standards repository source of truth

The repository SHALL store reusable AI workflow standards for DevOps / Platform Engineering rather than acting as the target consumer project.

#### Scenario: Agent starts in standards repository

- GIVEN the repository is checked out
- WHEN Codex or Claude Code starts in the root
- THEN root `AGENTS.md` and `CLAUDE.md` SHALL guide maintenance of the standards repository
- AND reusable global instructions SHALL live under `templates/`

### Requirement: Codex-first dual-agent workflow

The repository SHALL support Codex as the primary agent and Claude Code as a compatible secondary agent.

#### Scenario: Codex and Claude entry points exist

- GIVEN the repository is checked out
- WHEN an agent starts in the root
- THEN Codex SHALL find `AGENTS.md`
- AND Claude Code SHALL find `CLAUDE.md`
- AND personal global templates SHALL exist under `templates/codex/` and `templates/claude/`

### Requirement: Personal global sync

The repository SHALL provide an explicit personal sync script for linking global agent instructions and namespaced Codex review skills from this repository.

#### Scenario: Personal sync creates links

- GIVEN `CODEX_HOME` and `CLAUDE_HOME` point to writable directories
- WHEN `scripts/sync-personal-ai-config.sh` runs
- THEN it SHALL link Codex global `AGENTS.md` to `templates/codex/AGENTS.global.md`
- AND it SHALL link Claude Code global `CLAUDE.md` to `templates/claude/CLAUDE.global.md`
- AND it SHALL link namespaced Codex review skills under `CODEX_HOME/skills/`

#### Scenario: Destination exists

- GIVEN a destination file already exists
- WHEN sync runs without `--force`
- THEN it SHALL fail without modifying the destination

#### Scenario: Force sync is requested

- GIVEN a destination file already exists
- WHEN sync runs with `--force`
- THEN it SHALL back up the existing destination before creating the symlink

### Requirement: Conditional review skills

The repository SHALL provide custom conditional skills for architecture, security, and operational risk review.

#### Scenario: Security-sensitive files change

- GIVEN a change touches IAM, RBAC, secrets, credentials, or network policy
- WHEN the agent plans or reviews the change
- THEN it SHALL use `skills/security-review/SKILL.md`

### Requirement: Local validation scripts

The repository SHALL provide reusable scripts for common DevOps validation flows.

#### Scenario: Terraform changes exist

- GIVEN Terraform files are present
- WHEN `validations/terraform.sh` runs
- THEN it SHALL run non-destructive formatting and validation checks

### Requirement: Codex bootstrap checks

The repository SHALL provide a non-destructive setup check that can run automatically in a Codex session.

#### Scenario: Codex session starts with hooks enabled

- GIVEN `.codex/config.toml` enables `codex_hooks`
- WHEN Codex starts or resumes a session
- THEN the setup check SHALL report missing tools or config as additional context
- AND it SHALL not install packages or mutate global state
