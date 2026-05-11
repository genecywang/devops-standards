#!/usr/bin/env bash
set -euo pipefail

FORCE=0
DRY_RUN=0
SYNC_CODEX=1
SYNC_CLAUDE=1
SYNC_SKILLS=1

usage() {
  cat <<'USAGE'
Usage: scripts/sync-personal-ai-config.sh [options]

Synchronizes personal global AI assistant configuration from this repository.

Default behavior:
  - Link ~/.codex/AGENTS.md to templates/codex/AGENTS.global.md
  - Link ~/.claude/CLAUDE.md to templates/claude/CLAUDE.global.md
  - Link namespaced DevOps review skills into ~/.codex/skills/
  - Do not modify config.toml, settings.json, secrets, or credentials

Options:
  --force        Back up existing destinations before replacing them.
  --dry-run      Print planned changes without writing files.
  --codex-only   Sync Codex files only.
  --claude-only  Sync Claude Code files only.
  --with-skills  Sync namespaced Codex skill symlinks. This is the default.
  --no-skills    Do not sync Codex skill symlinks.
  -h, --help     Show this help.
USAGE
}

for arg in "$@"; do
  case "$arg" in
    --force)
      FORCE=1
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    --codex-only)
      SYNC_CODEX=1
      SYNC_CLAUDE=0
      ;;
    --claude-only)
      SYNC_CODEX=0
      SYNC_CLAUDE=1
      SYNC_SKILLS=0
      ;;
    --with-skills)
      SYNC_SKILLS=1
      ;;
    --no-skills)
      SYNC_SKILLS=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
codex_home="${CODEX_HOME:-$HOME/.codex}"
claude_home="${CLAUDE_HOME:-$HOME/.claude}"
timestamp="$(date +%Y%m%d%H%M%S)"

log() {
  printf '%s\n' "$*"
}

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    log "dry-run: $*"
    return 0
  fi

  "$@"
}

backup_path() {
  local destination="$1"
  local backup="${destination}.bak.${timestamp}"
  local counter=1

  while [ -e "$backup" ] || [ -L "$backup" ]; do
    backup="${destination}.bak.${timestamp}.${counter}"
    counter=$((counter + 1))
  done

  if [ "$DRY_RUN" -eq 1 ]; then
    log "would backup: $destination -> $backup"
    return 0
  fi

  mv "$destination" "$backup"
  log "backup: $destination -> $backup"
}

ensure_parent_dir() {
  local destination="$1"
  local parent
  parent="$(dirname "$destination")"
  run mkdir -p "$parent"
}

ensure_symlink() {
  local source="$1"
  local destination="$2"
  local label="$3"

  if [ ! -e "$source" ] && [ ! -L "$source" ]; then
    echo "missing source for $label: $source" >&2
    exit 1
  fi

  ensure_parent_dir "$destination"

  if [ -L "$destination" ]; then
    local current_target
    current_target="$(readlink "$destination")"

    if [ "$current_target" = "$source" ]; then
      log "ok: $label already linked"
      return 0
    fi

    if [ "$FORCE" -ne 1 ]; then
      echo "destination exists with different symlink target: $destination -> $current_target" >&2
      echo "rerun with --force to back it up and replace it" >&2
      exit 1
    fi

    backup_path "$destination"
  elif [ -e "$destination" ]; then
    if [ "$FORCE" -ne 1 ]; then
      echo "destination exists and will not be overwritten: $destination" >&2
      echo "rerun with --force to back it up and replace it" >&2
      exit 1
    fi

    backup_path "$destination"
  fi

  if [ "$DRY_RUN" -eq 1 ]; then
    log "would link: $destination -> $source"
    return 0
  fi

  ln -s "$source" "$destination"
  log "linked: $destination -> $source"
}

sync_codex() {
  ensure_symlink \
    "$repo_root/templates/codex/AGENTS.global.md" \
    "$codex_home/AGENTS.md" \
    "Codex global AGENTS.md"
}

sync_claude() {
  ensure_symlink \
    "$repo_root/templates/claude/CLAUDE.global.md" \
    "$claude_home/CLAUDE.md" \
    "Claude Code global CLAUDE.md"
}

sync_codex_skills() {
  ensure_symlink \
    "$repo_root/skills/architecture-review" \
    "$codex_home/skills/gene-devops-architecture-review" \
    "Codex architecture review skill"

  ensure_symlink \
    "$repo_root/skills/security-review" \
    "$codex_home/skills/gene-devops-security-review" \
    "Codex security review skill"

  ensure_symlink \
    "$repo_root/skills/operational-risk-review" \
    "$codex_home/skills/gene-devops-operational-risk-review" \
    "Codex operational risk review skill"
}

if [ "$SYNC_CODEX" -eq 1 ]; then
  sync_codex
fi

if [ "$SYNC_CLAUDE" -eq 1 ]; then
  sync_claude
fi

if [ "$SYNC_CODEX" -eq 1 ] && [ "$SYNC_SKILLS" -eq 1 ]; then
  sync_codex_skills
fi

log "personal AI config sync finished"
