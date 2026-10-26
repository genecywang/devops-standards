# devops-standards

DevOps / Platform Engineering AI-assisted workflow standards for Codex and Claude Code.

This repository is the **source of truth** for reusable standards, templates, conditional skills, workflow playbooks, and validation scripts. It is not meant to be treated as the consumer project itself.

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
| `docs/archive/openspec/` | Historical specs and change records; not active workflow requirements |
| `skills/` | Conditional review skills for architecture, security, and operational risk |
| `prompts/` | Reusable focused prompts; [structured task contracts](prompts/task-contracts.md) |
| `workflows/` | Human-readable workflow playbooks |
| `scripts/` | Personal sync, bootstrap, and environment check scripts |
| `setup/` | Optional adoption notes for Claude Code on macOS and Playwright MCP |
| `validations/` | Local non-destructive DevOps validation scripts |
| `tests/` | Shell and Python regression tests for standards tooling |

## Personal Fast Sync

Recommended personal setup:

```zsh
scripts/sync-personal-ai-config.sh
```

This creates symlinks:

```text
~/.codex/AGENTS.md -> templates/codex/AGENTS.global.md
~/.claude/CLAUDE.md -> templates/claude/CLAUDE.global.md
~/.codex/standards/{workflows,prompts,validations} -> matching repo directories
~/.claude/standards/{workflows,prompts,validations} -> matching repo directories
~/.agents/skills/gene-devops-architecture-review -> skills/architecture-review
~/.agents/skills/gene-devops-security-review -> skills/security-review
~/.agents/skills/gene-devops-operational-risk-review -> skills/operational-risk-review
```

The script does not touch `~/.codex/config.toml`, `~/.claude/settings.json`, secrets, credentials, or package managers.

If a destination already exists, the script stops without modifying it. To replace an existing file or symlink after reviewing the impact:

```zsh
scripts/sync-personal-ai-config.sh --force
```

`--force` backs up existing destinations before linking. Global instruction backups use
`.bak.<timestamp>` beside the original; skill backups go under the client configuration
root’s `skill-backups/`, outside the default discovery directories.

Useful variants:

```zsh
scripts/sync-personal-ai-config.sh --dry-run
scripts/sync-personal-ai-config.sh --codex-only
scripts/sync-personal-ai-config.sh --claude-only
scripts/sync-personal-ai-config.sh --no-skills
```

## Optional Skill Installer Entry

The shared `skills/install-skills` entry supports Codex and Claude Code. It routes explicit requests to the client's available installer or plugin tools; it does not install a fixed bundle or change models/permissions.

```zsh
# Preview, then enable only the Codex installer entry (skip review-skill sync)
bash scripts/sync-personal-ai-config.sh --codex-only --no-skills --with-installer --dry-run
bash scripts/sync-personal-ai-config.sh --codex-only --no-skills --with-installer

# Alternatively, include the optional entry in a normal sync for both clients
bash scripts/sync-personal-ai-config.sh --with-installer
```

Codex's optional entry is linked at `~/.agents/skills/gene-devops-install-skills`; override this destination with `CODEX_USER_SKILLS_DIR` when needed. Claude's entry is linked at `${CLAUDE_HOME:-$HOME/.claude}/skills/install-skills`. Existing destinations use the same no-overwrite and explicit `--force` backup rules as other sync targets. The optional entry is independent of `--no-skills`, which only skips the existing review-skill sync.

In Codex, select `install-skills` through `/skills` or use `$install-skills`; in Claude use `/install-skills`. For example: “只盤點目前已安裝的 skills，不安裝或修改設定。” For a specific install, name the client, skill/source, and scope. The built-in Codex `skill-installer`, when available, remains the installation backend; the two skill names serve different roles. Refresh discovery or start a new session if the entry is not visible.

## Repo-Local Codex Bootstrap

For this standards repo, create local Codex config when needed:

```zsh
scripts/check-codex-workflow.sh
scripts/bootstrap-codex-workflow.sh
```

Bootstrap preserves existing local configuration.

Recommended defaults:

- `sandbox_mode = "workspace-write"`
- `approval_policy = "on-request"`
- network disabled unless explicitly needed
- `features.hooks = true` (`features.codex_hooks` remains a compatible legacy alias)
- `SessionStart` hook only checks setup and does not install tools
- Python 3.11+ enables TOML inspection; unavailable inspection is reported explicitly
- Superpowers is optional; discovery does not prove runtime activation

For initial setup or setup troubleshooting, optionally use:

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

## Task Scope, Skills, and Models

Use the [AI coding workflow](workflows/ai-coding-workflow.md) to distinguish a bounded local fix from a significant policy, architecture, or infrastructure change. Keep production/shared-state approval gates even when the agent completes local preparation without repeated confirmation.

Both global templates organize complex natural-language tasks into goals, context, constraints, deliverables, completion criteria, and applicable environment/authorization without requiring a template path or form.

Both global templates request cost-aware delegation for useful independent work. Codex routes narrow tasks to Luna, general work to Sol, and difficult reasoning to Astra as needed; see [subagent routing](workflows/model-skill-evaluation.md#subagent-routing). This is an instruction policy, not a spending cap or a change to the active main model.

Both global templates explicitly override universal Superpowers loading and disproportionate planning/testing gates. The installed third-party bundle is not edited or uninstalled. Platform instructions still apply; verify the actual behavior in a new session. Existing symlinks expose updated templates and review skills without rerunning sync.

Use [structured task contracts](prompts/task-contracts.md) for outcome-based prompts and [model/skill evaluation](workflows/model-skill-evaluation.md) to compare a minimal baseline, selected skills, and the full bundle. Model and reasoning recommendations are evaluation candidates, not automatic configuration changes or measured performance claims.

Legacy duplicate Superpowers plans and the static Claude skill catalog have been retired. The installed `install-skills` entry point remains available for explicit requests; its old hook is a silent compatibility shim, not a recommended startup check. Historical specs and change records are preserved under `docs/archive/openspec/`; scripts no longer depend on them. No fixed proposal/specs/design/tasks or archive workflow is required. Use conversation, issue, PR, or focused design notes as appropriate to risk.

Bootstrap only creates missing repo-local config and runs setup inspection. It does not require Node.js, npm, or a specification CLI, install packages, or run infrastructure validation. Removed installation flags are rejected without performing writes.

## Validations

For changes spanning the supported infrastructure types, run all infra checks:

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
python3 -m unittest discover -s tests -p 'test_*.py'
```

Choose checks for the affected behavior; do not repeat passing checks without a new change or unresolved concern. The IAM script checks JSON syntax and selected wildcards, not effective permissions or full policy safety.

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

## Personal Setup Verification and Migration

Run `python3 scripts/check-personal-ai-config.py` after sync; add `--codex-only`
for a Codex-only setup, and `--with-installer` to require the optional installer.
This is a read-only link/discovery check, not proof of runtime skill activation.
All Codex review and installer links use `CODEX_USER_SKILLS_DIR` (default `~/.agents/skills`).
`CODEX_HOME` and `CLAUDE_HOME` override the client configuration roots independently.

For existing legacy review links, preview and migrate with:

```zsh
scripts/sync-personal-ai-config.sh --migrate-legacy-skills --dry-run
scripts/sync-personal-ai-config.sh --migrate-legacy-skills
```

Migration only accepts links to this checkout's review skills. It moves old links
into `~/.codex/skill-backups/<timestamp>/`, outside discovery, and preserves unrelated
skills. Restore those links manually if rolling back. Known destination conflicts
are checked before writing; unexpected filesystem failures are not transactional.

Symlinks immediately expose working-tree edits, including uncommitted changes.
For a stable daily baseline, sync from a separate checkout pinned to a reviewed
commit and update it deliberately. Keep that checkout at a stable path.

Kubernetes checks select candidate YAML with top-level `apiVersion` or `kind`, exclude
archives, dependencies, and Helm chart sources, and require kubeconform for
schema validation. Helm charts are validated separately with `validations/helm.sh`.
Kubeconform may fetch schemas; no cluster credentials or kubectl fallback are used.

## Global Resource Access from Other Projects

This repository distributes global instructions **and** on-demand supporting resources.
Sync creates the selected client's `standards/` directory with links to `workflows/`,
`prompts/`, and `validations/`, even with `--no-skills`. It does not expose the root
maintenance instructions as global project rules. Skills retain their existing installation paths.

The global templates explicitly tell agents where to read supporting documents:

```sh
cat "${CODEX_HOME:-$HOME/.codex}/standards/workflows/model-skill-evaluation.md"
# Claude: ${CLAUDE_HOME:-$HOME/.claude}/standards/workflows/model-skill-evaluation.md
```

These paths work independently of the current directory. A new session still needs
its client to load the global instructions and permit reading the resources; a symlink
does not bypass a sandbox. Content is loaded on demand, not automatically injected
in full. Resolve the document’s physical path before following relative links,
so references such as `../README.md` reach the source checkout rather than a
nonexistent file under the `standards/` alias. Source checkout edits are immediately visible. After moving the checkout,
rerun sync from its new location; review `--dry-run` and use `--force` only when needed.
The personal checker detects missing, broken, or wrong-target resource links.

Existing installations need one sync to create these entries. Existing destination
conflicts are checked before writes, and `--force` preserves backups. To roll back,
remove only the three installed resource links and restore any backed-up destinations;
never recursively delete through a link. Keep target-project instructions authoritative.
