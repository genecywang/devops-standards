# Personal AI Config Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert this repository into a standards source of truth that can quickly sync personal Codex and Claude Code global instructions through explicit symlinks.

**Architecture:** Keep repo-root `AGENTS.md` and `CLAUDE.md` focused on maintaining this standards repository. Store reusable global templates under `templates/`, and add one safe sync script that links those templates into `~/.codex` and `~/.claude` without overwriting existing local files unless `--force` is used.

**Tech Stack:** Bash, symlinks, Codex global `AGENTS.md`, Claude Code global `CLAUDE.md`, shell-based tests.

---

### Task 1: Add Sync Script Tests

**Files:**
- Create: `tests/sync-personal-ai-config.test.sh`

- [ ] **Step 1: Write test for new symlink creation**

Create a shell test that runs the sync script with temporary `CODEX_HOME` and `CLAUDE_HOME`, then verifies:

```text
CODEX_HOME/AGENTS.md -> templates/codex/AGENTS.global.md
CLAUDE_HOME/CLAUDE.md -> templates/claude/CLAUDE.global.md
CODEX_HOME/skills/gene-devops-architecture-review -> skills/architecture-review
CODEX_HOME/skills/gene-devops-security-review -> skills/security-review
CODEX_HOME/skills/gene-devops-operational-risk-review -> skills/operational-risk-review
```

- [ ] **Step 2: Write test for non-overwrite behavior**

Create a file at `CODEX_HOME/AGENTS.md`, run the script without `--force`, and verify it exits non-zero while leaving the file unchanged.

- [ ] **Step 3: Write test for forced backup behavior**

Create files at `CODEX_HOME/AGENTS.md` and `CLAUDE_HOME/CLAUDE.md`, run the script with `--force`, and verify `.bak.<timestamp>` files exist and the final destinations are symlinks.

- [ ] **Step 4: Verify RED**

Run:

```zsh
bash tests/sync-personal-ai-config.test.sh
```

Expected: fail because `scripts/sync-personal-ai-config.sh` does not exist yet.

### Task 2: Add Personal Sync Script

**Files:**
- Create: `scripts/sync-personal-ai-config.sh`

- [ ] **Step 1: Implement CLI options**

Support:

```text
--force
--dry-run
--codex-only
--claude-only
--with-skills
--no-skills
--help
```

Defaults: sync Codex and Claude global instruction symlinks plus namespaced Codex skill symlinks. Do not touch `config.toml` or Claude settings by default.

- [ ] **Step 2: Implement safe link behavior**

For each destination:

```text
correct symlink already exists -> print ok
destination missing -> create parent dir and symlink
destination exists and --force missing -> fail without modifying
destination exists and --force present -> move to .bak.<timestamp>, then symlink
```

- [ ] **Step 3: Verify GREEN**

Run:

```zsh
bash tests/sync-personal-ai-config.test.sh
```

Expected: pass.

### Task 3: Add Global Templates

**Files:**
- Create: `templates/codex/AGENTS.global.md`
- Create: `templates/claude/CLAUDE.global.md`
- Create: `templates/codex/config.example.toml`
- Create: `templates/claude/settings.example.json`

- [ ] **Step 1: Add global instruction templates**

Move reusable DevOps / Platform Engineer guidance into global templates. Make clear that project-local `AGENTS.md` or `CLAUDE.md` can override or extend these instructions.

- [ ] **Step 2: Add config examples**

Copy existing examples under `templates/` for distribution, while keeping root `.codex/` and `.claude/` examples available for this repository.

### Task 4: Reposition Repository Documentation

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `prompts/bootstrap/codex-workflow.md`
- Modify: `openspec/config.yaml`
- Modify: `openspec/specs/ai-coding-workflow/spec.md`
- Modify: `openspec/changes/bootstrap-codex-claude-workflow/design.md`
- Modify: `openspec/changes/bootstrap-codex-claude-workflow/tasks.md`

- [ ] **Step 1: Update root entry points**

Make root `AGENTS.md` and `CLAUDE.md` explain that this repo maintains standards, templates, skills, workflows, and validations. Avoid wording that treats this repository as the consumer project.

- [ ] **Step 2: Update user-facing docs**

Document the recommended personal sync command:

```zsh
scripts/sync-personal-ai-config.sh
```

Document force mode and verification:

```zsh
scripts/sync-personal-ai-config.sh --force
scripts/check-codex-workflow.sh
```

- [ ] **Step 3: Update OpenSpec language**

Change wording from repo-local project setup to standards distribution and personal global sync.

### Task 5: Verify

**Files:**
- All changed files

- [ ] **Step 1: Run shell syntax checks**

Run:

```zsh
bash -n scripts/check-codex-workflow.sh scripts/bootstrap-codex-workflow.sh scripts/sync-personal-ai-config.sh validations/*.sh tests/sync-personal-ai-config.test.sh
```

- [ ] **Step 2: Run script tests**

Run:

```zsh
bash tests/sync-personal-ai-config.test.sh
```

- [ ] **Step 3: Run workflow checks**

Run:

```zsh
scripts/check-codex-workflow.sh
scripts/check-codex-workflow.sh --hook
validations/all.sh
git diff --check
```

OpenSpec validation is optional until the user approves installing the global `openspec` CLI.
