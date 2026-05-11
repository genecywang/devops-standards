# Codex Bootstrap Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe Codex bootstrap workflow that checks and installs OpenSpec and enables repo-local workflow skills with explicit user control.

**Architecture:** A non-destructive check script runs safely from a Codex `SessionStart` hook and reports missing setup. A separate bootstrap script performs controlled setup, including optional global OpenSpec installation, local `.codex/config.toml` creation, and validation runs.

**Tech Stack:** POSIX shell / Bash, Codex `config.toml` hooks, OpenSpec CLI, local repo skills.

---

### Task 1: Add Bootstrap Scripts

**Files:**
- Create: `scripts/check-codex-workflow.sh`
- Create: `scripts/bootstrap-codex-workflow.sh`

- [ ] **Step 1: Create `check-codex-workflow.sh`**

The script checks Node.js, OpenSpec, Codex config, local skills, superpowers installation hint, and validation script permissions. It supports `--hook` mode that exits `0` and emits JSON additional context for Codex.

- [ ] **Step 2: Create `bootstrap-codex-workflow.sh`**

The script creates `.codex/config.toml` from `.codex/config.example.toml`, optionally installs OpenSpec with `--install-openspec`, validates OpenSpec when available, and runs `validations/all.sh`.

- [ ] **Step 3: Run shell syntax checks**

Run:

```zsh
bash -n scripts/check-codex-workflow.sh scripts/bootstrap-codex-workflow.sh
```

Expected: exit `0`.

### Task 2: Add Codex Startup Guidance

**Files:**
- Create: `prompts/bootstrap/codex-workflow.md`
- Modify: `.codex/config.example.toml`

- [ ] **Step 1: Add bootstrap prompt**

The prompt tells a new Codex session to run `scripts/check-codex-workflow.sh` first, then run `scripts/bootstrap-codex-workflow.sh` only when setup is missing and the user approves.

- [ ] **Step 2: Add `SessionStart` hook example**

Add `features.codex_hooks = true` and a `SessionStart` hook in `.codex/config.example.toml` that runs:

```zsh
bash "$(git rev-parse --show-toplevel)/scripts/check-codex-workflow.sh" --hook
```

Expected: the hook only reports missing setup; it does not install tools.

### Task 3: Update Documentation And Specs

**Files:**
- Modify: `README.md`
- Modify: `openspec/changes/bootstrap-codex-claude-workflow/tasks.md`
- Modify: `openspec/specs/ai-coding-workflow/spec.md`

- [ ] **Step 1: Document bootstrap usage**

Add commands for checking, bootstrapping, and new session validation.

- [ ] **Step 2: Update OpenSpec artifacts**

Record the new bootstrap scripts and startup prompt in the active change tasks and living spec.

### Task 4: Verify

**Files:**
- All changed files

- [ ] **Step 1: Run script syntax checks**

Run:

```zsh
bash -n scripts/check-codex-workflow.sh scripts/bootstrap-codex-workflow.sh validations/*.sh
```

- [ ] **Step 2: Run check script**

Run:

```zsh
scripts/check-codex-workflow.sh
scripts/check-codex-workflow.sh --hook
```

- [ ] **Step 3: Run bootstrap dry path**

Run:

```zsh
scripts/bootstrap-codex-workflow.sh --skip-openspec-install
```

- [ ] **Step 4: Run validation suite**

Run:

```zsh
validations/all.sh
git diff --check
```
