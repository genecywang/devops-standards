# Bootstrap Codex And Claude Workflow Design

## Architecture

The repository is split into six layers:

- Repository maintenance entry points: root `AGENTS.md` for Codex and root `CLAUDE.md` for Claude Code.
- Reusable global templates: `templates/codex/AGENTS.global.md` and `templates/claude/CLAUDE.global.md` for personal symlink sync.
- Planning layer: `openspec/` for living specs and change artifacts.
- Conditional execution guidance: `skills/` and `prompts/`.
- Deterministic validation: `validations/` shell scripts.
- Bootstrap and setup checks: `scripts/`.

## Key Decisions

### Root entry points are not global templates

Root `AGENTS.md` and `CLAUDE.md` describe how to maintain this standards repository. They are not intended to be symlinked into global assistant homes or copied directly into consumer repositories.

Trade-off: maintaining root entry points and global templates introduces drift risk. Mitigation is to keep root files focused on repository maintenance and keep reusable baseline guidance under `templates/`.

### Personal global sync uses symlinks

For personal fast sync, `~/.codex/AGENTS.md` and `~/.claude/CLAUDE.md` can point to versioned templates in this repository. This makes updates immediate after pulling the repo.

Trade-off: symlinks are not ideal for team distribution because they hide version ownership from target repositories. Mitigation is to use symlinks only for personal global config; consumer repositories should copy or install templates and review them locally.

### Config files are not symlinked by default

Codex `config.toml` and Claude settings may contain local sandbox, approval, hook, and permission choices. The sync script does not touch them by default. Example config files remain versioned for review and manual adoption.

### OpenSpec owns intent, not execution

OpenSpec artifacts capture proposal, requirements, design, and tasks. They do not grant permission to mutate infrastructure. Approval gates remain in the agent instructions and workflow docs.

### Skills are conditional

Architecture, security, and operational risk reviews are custom skills because they require judgment. They are not always-on because loading all review checklists into every session would waste context.

For personal Codex usage, the sync script links these skills under namespaced directories:

- `gene-devops-architecture-review`
- `gene-devops-security-review`
- `gene-devops-operational-risk-review`

### Validation scripts are local and conservative

Scripts are designed for local validation and static checks. They do not run write operations against Terraform state, Kubernetes clusters, Helm releases, or AWS APIs.

### Bootstrap separates checks from installation

`scripts/check-codex-workflow.sh` is safe to run from Codex `SessionStart`; it reports missing setup and exits without changing global state. `scripts/bootstrap-codex-workflow.sh` performs setup only when invoked directly, and OpenSpec installation requires `--install-openspec` or interactive confirmation.

### Personal sync is reversible

`scripts/sync-personal-ai-config.sh` refuses to overwrite existing destinations by default. With `--force`, it moves the destination to `.bak.<timestamp>` before creating the symlink.

## Rollback

Rollback is a git revert of the repository changes. For personal sync, restore the generated `.bak.<timestamp>` file or remove the symlink manually. If OpenSpec was installed globally through the bootstrap script, remove it with the package manager outside this repository. No production or shared infrastructure state is modified by this change.

## Observability

No runtime observability changes are required. Validation evidence is produced by local commands and git diff.
