# Bootstrap Codex And Claude Workflow Proposal

## Why

The repository should move from ad hoc copied instruction files into a maintainable standards source of truth that is Codex-first while still supporting Claude Code. The workflow needs explicit planning, validation, review, and approval gates for DevOps and Platform Engineering work, while also supporting personal fast sync through global symlinks.

## What

- Keep root `AGENTS.md` and `CLAUDE.md` as standards-repository maintenance entry points.
- Add global templates under `templates/codex/` and `templates/claude/` for personal symlink sync.
- Add `scripts/sync-personal-ai-config.sh` for reversible personal global sync.
- Add OpenSpec living specs for AI coding workflow and infrastructure change management.
- Add conditional review skills for architecture, security, and operational risk.
- Add reusable workflow documentation and validation scripts.
- Add example agent configuration files without committing machine-local config.

## Scope

In scope:

- Repository structure and documentation.
- Personal global instruction sync script.
- Global Codex and Claude Code templates.
- OpenSpec configuration and initial specs.
- Local validation scripts.
- Codex / Claude Code compatible skill folders.

Out of scope:

- Installing OpenSpec globally.
- Running production or shared infrastructure commands.
- Adding remote CI/CD automation.
- Modifying secrets or credentials.
- Automatically overwriting existing `~/.codex` or `~/.claude` files.

## Success Criteria

- Codex and Claude Code have clear entry points.
- Personal global templates can be linked from `~/.codex` and `~/.claude`.
- Existing global files are not overwritten unless `--force` is used and backups are created.
- Meaningful infra changes have a documented OpenSpec path.
- Conditional skills are available without always injecting heavy context.
- Validation scripts are executable and safe for local dry-run use.
- README explains how to operate the workflow.

## Risks

- Overly verbose instructions could pollute context.
- Inaccurate validation scripts could produce false confidence.
- Root entry points and global templates could drift over time.
- Personal sync could overwrite valuable local settings if not constrained.

Mitigation:

- Keep entry points short and put detailed procedures in `workflows/`.
- Scripts skip cleanly when no matching files exist and report missing tools.
- Root files and templates explicitly state their intended scope.
- Personal sync defaults to no-overwrite and requires `--force` for backup-and-replace behavior.
