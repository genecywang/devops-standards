# devops-standards

DevOps / Platform Engineering AI-assisted workflow standards for Codex and Claude Code.

This repository is the **source of truth** for reusable standards, templates, OpenSpec artifacts, conditional skills, workflow playbooks, and validation scripts. It is not meant to be treated as the consumer project itself.

## Contents

| Path | Purpose |
|---|---|
| `AGENTS.md` | Codex guidance for maintaining this standards repository |
| `CLAUDE.md` | Claude Code guidance for maintaining this standards repository |
| `templates/codex/AGENTS.global.md` | Personal global Codex baseline, suitable for `~/.codex/AGENTS.md` symlink |
| `templates/claude/CLAUDE.global.md` | Personal global Claude Code baseline, suitable for `~/.claude/CLAUDE.md` symlink |
| `templates/codex/config.example.toml` | Example Codex config for consumer repos |
| `templates/claude/settings.example.json` | Example Claude Code permission guardrails |
| `.codex/config.example.toml` | Example repo-local Codex config for this standards repo |
| `.claude/settings.example.json` | Example repo-local Claude Code permission guardrails |
| `openspec/` | Living specs and change artifacts for this standards system |
| `skills/` | Conditional review skills for architecture, security, and operational risk |
| `prompts/` | Reusable focused prompts |
| `workflows/` | Human-readable workflow playbooks |
| `scripts/` | Personal sync, bootstrap, and environment check scripts |
| `validations/` | Local non-destructive DevOps validation scripts |
| `tests/` | Shell tests for standards tooling |

## Personal Fast Sync

Recommended personal setup:

```zsh
scripts/sync-personal-ai-config.sh
```

This creates symlinks:

```text
~/.codex/AGENTS.md -> templates/codex/AGENTS.global.md
~/.claude/CLAUDE.md -> templates/claude/CLAUDE.global.md
~/.codex/skills/gene-devops-architecture-review -> skills/architecture-review
~/.codex/skills/gene-devops-security-review -> skills/security-review
~/.codex/skills/gene-devops-operational-risk-review -> skills/operational-risk-review
```

The script does not touch `~/.codex/config.toml`, `~/.claude/settings.json`, secrets, credentials, or package managers.

If a destination already exists, the script stops without modifying it. To replace an existing file or symlink after reviewing the impact:

```zsh
scripts/sync-personal-ai-config.sh --force
```

`--force` moves existing destinations to `.bak.<timestamp>` before linking.

Useful variants:

```zsh
scripts/sync-personal-ai-config.sh --dry-run
scripts/sync-personal-ai-config.sh --codex-only
scripts/sync-personal-ai-config.sh --claude-only
scripts/sync-personal-ai-config.sh --no-skills
```

## Repo-Local Codex Bootstrap

For this standards repo, create local Codex config when needed:

```zsh
scripts/check-codex-workflow.sh
scripts/bootstrap-codex-workflow.sh
```

Install OpenSpec explicitly when missing:

```zsh
scripts/bootstrap-codex-workflow.sh --install-openspec
```

The install path runs:

```zsh
npm install -g @fission-ai/openspec@latest
```

Review before approving because it modifies the global npm environment.

Manual repo-local config setup:

```zsh
mkdir -p .codex
cp .codex/config.example.toml .codex/config.toml
```

Recommended defaults:

- `sandbox_mode = "workspace-write"`
- `approval_policy = "on-request"`
- network disabled unless explicitly needed
- `SessionStart` hook only checks setup and does not install tools

For a new Codex session in this repo, use:

```zsh
prompts/bootstrap/codex-workflow.md
```

## Consumer Repo Adoption

For another infra / platform repo, do not symlink its project-local `AGENTS.md` to your global file. Prefer copying or installing templates so the target repo can review and own its own rules:

```text
templates/codex/AGENTS.global.md        -> target repo AGENTS.md baseline
templates/claude/CLAUDE.global.md       -> target repo CLAUDE.md baseline
templates/codex/config.example.toml     -> target repo .codex/config.example.toml
templates/claude/settings.example.json  -> target repo .claude/settings.example.json
skills/                                 -> target repo skills/
workflows/                              -> target repo workflows/
validations/                            -> target repo validations/
```

Project-local instructions should describe the target repo's actual deploy path, validation commands, ownership, and production approval gates.

## OpenSpec Setup

OpenSpec requires Node.js `20.19.0` or newer.

If OpenSpec CLI is installed:

```zsh
openspec validate bootstrap-codex-claude-workflow --strict
openspec list
```

If the CLI is not installed, the repository still keeps the documented OpenSpec structure:

```text
openspec/
├── config.yaml
├── specs/
└── changes/
```

## Validations

Run all local checks:

```zsh
validations/all.sh
```

Run focused checks:

```zsh
validations/terraform.sh
validations/helm.sh
validations/kubernetes.sh
validations/iam.sh
```

Run standards tooling tests:

```zsh
bash tests/sync-personal-ai-config.test.sh
```

These scripts are non-destructive. They do not run Terraform apply, Kubernetes writes, Helm release mutation, or AWS write APIs.

## Approval Boundaries

Agent may run:

- local read-only checks
- lint, test, format
- Terraform fmt / validate / plan
- Helm lint / template
- Kubernetes static validation / client dry-run

Human approval required:

- Terraform apply / destroy / import / state mutation
- kubectl apply / delete / edit / patch / rollout
- Helm install / upgrade / uninstall / rollback
- AWS writes, especially IAM, RDS, KMS, S3 policy, Security Group, Route53
- production or shared-state deploy / rollback
- secret or credential access

## Tech Stack

AWS (EKS, RDS, S3, IAM, MSK) · Kubernetes (Helm, Karpenter) · Terraform · Jenkins · ArgoCD · KEDA · Prometheus · Fluent-bit · OpenSearch
